#!/usr/bin/env python3
r"""公网 v1 线（Cloudflare Pages Function）的成本闸行为判据（r168 新增）。

**这条为什么存在**（不是又一层装饰）：
`/api/chat` 是本仓唯一真花钱的端点。Java 侧自 r128 起有令牌桶、r130 起有按日总量闸，
而公网那条线 —— 评委实际打的那条（`xinyu-soulisle.pages.dev` → `deploy/functions/api/chat.js`）——
r130 §9 一手实测登记：**既没有令牌桶也没有按日累计**，公网面当时只剩「密钥不落前端」一层。
r130 把三条出路列成表后顺延（当时的前提是「部署面有他人 DIFF」），此后没人销账。
本轮函数面 src⇄deploy 逐文件 SHA256 全等（实测见 `deploy_sync_check` 的函数出口面），
前提解除 ⇒ 落 r130 §9 的**选项③**（零新依赖、零部署面改动），并按**选项②**的口径把能力边界写进文档。

**这把尺测的是行为不是存在**（本仓 xinyu-benchmark-existence-vs-behaviour 记的口径陷阱）：
去 node 里用**假 fetch + 假时钟**驱动真函数模块，八个场景逐条读响应，
而不是 grep 一句「chat.js 里有 rate 字样」就记一格能力。

⚠️ 能力边界（写在这里，也写在 `docs/data-and-privacy.md`，且必须带取证命令）：
本闸只在**单个 isolate 的内存**里计数 ⇒ 冷启动即归零、换 IP 即绕开、没有按日累计。
它压得住「同一 IP 在一个 isolate 活着时猛打」，压不住慢速长期白嫖。
按日累计要 KV/D1 绑定，那属对外发布动作（r130 §9 选项①），本轮未做、未部署、未发布。

退出码：0=V1-COST-GUARD-PASS 1=任一红 2=环境未验（node 或函数源不可用，不得声称已验）
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
FN = ROOT / "src" / "functions" / "api" / "chat.js"

# 假时钟 + 假 fetch，八个场景按序打真函数模块。每个场景自带独立 IP ⇒ 桶互不干扰，
# 于是整个套件可以在**同一个 node 进程**里跑完（模块级 Map 只增不换进程重置，
# 靠 IP 隔离而不是靠重启，免得"场景间互相污染"这种假红再来一次）。
HARNESS = r"""
const RealNow = Date.now;
let T = 1700000000000;
Date.now = () => T;
const adv = (ms) => { T += ms; };

import(%(fnurl)s).then(async (mod) => {
  const out = [];
  const call = async (name, env, ip, body) => {
    globalThis.fetch = async () => new Response(JSON.stringify({ id: "stub", choices: [] }), {
      status: 200, headers: { "content-type": "application/json" } });
    const req = new Request("https://x/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json", "cf-connecting-ip": ip },
      body: JSON.stringify(body || { messages: [] }),
    });
    let r, err = null;
    try {
      r = await mod.onRequestPost({ request: req, env, params: {}, waitUntil() {}, ctx: {}, cf: {}, next() {} });
    } catch (e) { err = String((e && e.message) || e); }
    const h = {};
    if (r) for (const [k, v] of r.headers.entries()) h[k.toLowerCase()] = v;
    out.push({ name, status: r ? r.status : null, hdr: h,
               body: r ? await r.clone().text() : null, err, limit: h["x-ratelimit-limit"],
               left: h["x-ratelimit-remaining"], retry: h["retry-after"] });
  };
  const K = { DEEPSEEK_KEY: "stub-key" };
  const withMax = (m) => Object.assign({}, K, { LLM_MAX_PER_MIN: m });

  // L1 额度内放行且剩余额度递减
  T = 1700000000000;
  await call("l1a", withMax(3), "10.0.0.1");
  await call("l1b", withMax(3), "10.0.0.1");
  await call("l1c", withMax(3), "10.0.0.1");
  // L2 到顶即拒（第 4 次，limit 已耗尽）
  await call("l2", withMax(3), "10.0.0.1");
  // L3 被拒那次不得占用额度（否则越重试越早锁死 —— r130 S2 同族）
  await call("l3", withMax(3), "10.0.0.1");
  // L4 窗口滚过 ⇒ 恢复放行
  adv(61000);
  await call("l4", withMax(3), "10.0.0.1");
  // L5 不同 IP 各自成桶：A 打满不影响 B
  T = 1700000200000;
  await call("l5a", withMax(1), "10.0.0.2");
  await call("l5b", withMax(1), "10.0.0.2");
  await call("l5c", withMax(1), "10.0.0.3");
  // L6 关闸（0 = 不限）：连打 50 次必须全放行，判据夹具与演示可显式关
  T = 1700000300000;
  for (let i = 0; i < 50; i++) await call("l6", withMax(0), "10.0.0.4");
  // L7 缺 cf-connecting-ip 不崩（落 unknown 桶）
  T = 1700000400000;
  const req7 = new Request("https://x/api/chat", {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ messages: [] }) });
  globalThis.fetch = async () => new Response(JSON.stringify({ id: "stub" }), {
    status: 200, headers: { "content-type": "application/json" } });
  let r7, e7 = null;
  try { r7 = await mod.onRequestPost({ request: req7, env: withMax(2), params: {}, waitUntil() {}, ctx: {}, cf: {}, next() {} }); }
  catch (e) { e7 = String((e && e.message) || e); }
  out.push({ name: "l7", status: r7 ? r7.status : null, hdr: {}, body: r7 ? await r7.clone().text() : null, err: e7 });
  // L8 默认上限（env 完全不给 LLM_MAX_PER_MIN 时走代码默认）
  T = 1700000500000;
  await call("l8", K, "10.0.0.5");
  Date.now = RealNow;
  console.log(JSON.stringify(out));
});
"""


def probe(fn_path: Path):
    try:
        v = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=20)
    except Exception as exc:
        raise RuntimeError("node 不可调用: %s" % type(exc).__name__)
    if v.returncode != 0:
        raise RuntimeError("node --version rc=%s" % v.returncode)
    with tempfile.TemporaryDirectory() as td:
        h = Path(td) / "harness.mjs"
        h.write_text(HARNESS % {"fnurl": json.dumps(fn_path.as_uri())}, encoding="utf-8")
        try:
            r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
        except Exception as exc:
            raise RuntimeError("node 驱具执行异常: %s" % type(exc).__name__)
    if r.returncode != 0:
        raise RuntimeError("node 驱具 rc=%s stderr=%s" % (r.returncode, (r.stderr or "")[:200]))
    try:
        rows = json.loads(r.stdout.strip())
    except Exception as exc:
        raise RuntimeError("驱具输出非 JSON（%s）: %s" % (type(exc).__name__, r.stdout[:200]))
    return {x["name"]: x for x in rows}, rows


def assess(by, rows) -> list:
    """纯判定：八条场景逐条断言。返回红项名单（空 = 全过）。

    ⚠️ 分母取 **rows（全量读数）**而不是 by（按名字典）：L6 那 50 次同名读数在字典里会塌成 1 条，
    「跑满 50 次」这件事就永远量不到 —— 计数型断言的分母必须由被审对象自报。
    """
    bad = []

    def g(name):
        row = by.get(name)
        if row is None:
            bad.append("场景 %s 无读数 ⇒ 驱具没跑到它（不得据此记 PASS）" % name)
        return row or {}

    for n in ("l1a", "l1b", "l1c", "l2", "l3", "l4", "l5a", "l5b", "l5c", "l7", "l8"):
        if g(n).get("err"):
            bad.append("%s 抛错: %s" % (n, g(n)["err"][:80]))

    # L1 放行三次，剩余额度必须 2→1→0（计数真的把额度占掉了）
    lefts = [g("l1a").get("left"), g("l1b").get("left"), g("l1c").get("left")]
    if [str(x) for x in lefts] != ["2", "1", "0"]:
        bad.append("L1 剩余额度序列应为 2/1/0，实测 %s ⇒ 计数没生效或把额度算错" % lefts)
    for n in ("l1a", "l1b", "l1c"):
        if g(n).get("status") != 200:
            bad.append("L1 %s 期望 200，实测 %s" % (n, g(n).get("status")))

    # L2/L3 到顶即拒：429 + 契约错误体 + Retry-After 为正整数
    for n in ("l2", "l3"):
        row = g(n)
        if row.get("status") != 429:
            bad.append("%s 期望 429（额度已耗尽），实测 %s ⇒ 闸没拦" % (n, row.get("status")))
        if "rate-limited" not in (row.get("body") or ""):
            bad.append("%s 错误体不含 rate-limited（契约要的是 {\"error\":\"rate-limited\"}）: %r"
                       % (n, (row.get("body") or "")[:60]))
        try:
            assert int(row.get("retry") or 0) >= 1
        except Exception:
            bad.append("%s 的 Retry-After 缺失或 <1：%r ⇒ 客户端无法判断该等多久" % (n, row.get("retry")))

    # L3 被拒那次不得继续吃额度：remaining 仍是 0 而不是 -1（负数=被拒也计数）
    if str(g("l3").get("left")) != "0":
        bad.append("L3 被拒后 remaining=%r（期望恒为 0）⇒ 被拒那次也在计数，越重试越早锁死"
                   % g("l3").get("left"))

    # L4 窗口滚过必须恢复
    if g("l4").get("status") != 200:
        bad.append("L4 窗口滚过 61s 后仍 %s（期望 200）⇒ 窗口不滚动 / 计数器不重置"
                   % g("l4").get("status"))

    # L5 按 IP 成桶
    if g("l5a").get("status") != 200 or g("l5b").get("status") != 429:
        bad.append("L5 IP-A 序列应 200,429，实测 %s,%s" % (g("l5a").get("status"), g("l5b").get("status")))
    if g("l5c").get("status") != 200:
        bad.append("L5 IP-B 被 IP-A 的额度连坐（实测 %s）⇒ 桶没按 IP 分" % g("l5c").get("status"))

    # L6 关闸后 50 次全放行
    l6 = [x for x in rows if x["name"] == "l6"]
    if len(l6) != 50:
        bad.append("L6 关闸场景读数 %d 条 ≠ 50 ⇒ 驱具没跑满" % len(l6))
    elif any(r["status"] != 200 for r in l6):
        bad.append("L6 LLM_MAX_PER_MIN=0 仍被拦（%d 条非 200）⇒ 关闸开关失效，会打断演示与判据夹具"
                   % sum(1 for r in l6 if r["status"] != 200))

    # L8 默认值必须宽松（本仓铁律：默认值宁可多花也不能打断既有回归与评委）
    if str(g("l8").get("limit") or "") == "":
        bad.append("L8 未给 LLM_MAX_PER_MIN 时没有 X-RateLimit-Limit ⇒ 默认上限不可观测")
    else:
        dflt = int(g("l8")["limit"])
        if dflt < 20:
            bad.append("L8 默认上限被调到 %d（下限 20）⇒ 默认值不再宽松，会打断评委与电池自调用" % dflt)
    return bad


def run() -> int:
    if not FN.is_file():
        print("V1-COST-GUARD-UNVERIFIED: 函数权威源不存在 -> %s" % FN)
        return 2
    try:
        by, rows = probe(FN)
    except RuntimeError as exc:
        print("V1-COST-GUARD-UNVERIFIED: %s ⇒ 环境不满足，不判绿也不判红" % exc)
        return 2
    bad = assess(by, rows)
    for x in bad:
        print("  ✗ " + x)
    if bad:
        print("V1-COST-GUARD-FAIL: 红 %d 条｜场景读数 %d 条" % (len(bad), len(rows)))
        return 1
    print("V1-COST-GUARD-PASS: 8 场景 %d 条读数全过（额度递减/到顶即拒/被拒不计数/窗口滚动恢复/"
          "按 IP 分桶/0=关闸 50 次全放行/缺 IP 不崩/默认上限 %s 且可观测）"
          % (len(rows), by.get("l8", {}).get("limit")))
    return 0


# 变异腿：每条只改一处源码，改完必须让指定场景翻红。全部在**临时副本**上做，
# 绝不改 src/functions（r168 S1 刚为这件事返工过一条判据，同一课不上第二次）。
MUTATIONS = [
    ("摘掉到顶即拒的判断", "if (rec.n >= rpm) {", "if (false) {", ["l2"]),
    ("放行时不再计数", "  rec.n += 1;\n", "", ["L1"]),
    ("窗口拉长到一小时（滚动恢复失效）", "const RL_WINDOW_MS = 60000;", "const RL_WINDOW_MS = 3600000;",
     ["L4"]),
    ("默认上限调到 3（不再宽松）", "? limit : 30;", "? limit : 3;", ["L8"]),
    ("额度头不再回写", '    "X-RateLimit-Remaining": String(g.left),\n', "", ["L1"]),
]


def selftest() -> int:
    if not FN.is_file():
        print("V1-COST-GUARD-SELFTEST-FAIL: 读不到函数源，无法证伪")
        return 2
    src = FN.read_text(encoding="utf-8")
    bad = []
    # 反向腿①：原样副本必须全绿（否则下面的「变异被抓到」是在打一个本来就红的靶子）
    with tempfile.TemporaryDirectory() as td0:
        p0 = Path(td0) / "chat.js"
        p0.write_text(src, encoding="utf-8")
        try:
            base_by, base_rows = probe(p0)
        except RuntimeError as exc:
            print("V1-COST-GUARD-SELFTEST-FAIL: 原样驱具跑不动：%s" % exc)
            return 2
        if assess(base_by, base_rows):
            bad.append("反向腿①：未改动的副本被判红（判据有假阳性）：%s" % assess(base_by, base_rows)[:2])
    for label, old, new, must_flip in MUTATIONS:
        if src.count(old) != 1:
            bad.append("%s：锚点在源码里出现 %d 次（≠1）⇒ 变异可能空操作" % (label, src.count(old)))
            continue
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "chat.js"
            p.write_text(src.replace(old, new, 1), encoding="utf-8")
            try:
                by, rows = probe(p)
            except RuntimeError as exc:
                bad.append("%s：驱具失败 %s" % (label, exc))
                continue
            flipped = assess(by, rows)
            if not flipped:
                bad.append("%s：摘掉后八场景仍全绿 ⇒ 该腿是装饰，判据恒真" % label)
            else:
                hit = json.dumps(flipped, ensure_ascii=False)
                if not all(s in hit for s in must_flip):
                    bad.append("%s：翻红了但没点到应红场景 %s（红因=%s）" % (label, must_flip, hit[:120]))
    # 反向腿②：源码没被本轮写过
    if FN.read_text(encoding="utf-8") != src:
        bad.append("自噬：--selftest 改动了函数权威源 src/functions/api/chat.js")
    print("V1-COST-GUARD-SELFTEST-%s（%d 类变异 + 2 条反向腿，锚点按整段匹配）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(MUTATIONS)))
    for x in bad:
        print("  ✗ " + x)
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(run())
