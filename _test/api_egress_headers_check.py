#!/usr/bin/env python3
r"""函数出口安全头常驻判据（r59，接 r57 挂了两轮的中优先项）。

r57 把 `/api/chat`（Pages Function）的 5 条安全头补上了，取证是**一次手工 curl**。
手工取证不进体系 ⇒ 下一轮改函数把 `SEC_JSON` 漏在某个出口上，没有任何东西会红。
`headers_csp_check` 测的是静态 `_headers` 的页面入口，函数路径明确不吃它（r54 实测）。

为什么做成本地判据而不是 `--live` 线上 curl（这是本轮的一个判断，不是省事）
------------------------------------------------------------
1. 线上 curl 一天里可以时通时不通（本仓 [[reference-github-pages-blocked]] 实测口径），
   挂进阻断链就是给 CI 发一张随机彩票；
2. 线上只有**真实上游**那一条出口能被测到，而 r57 的 G3 明写要「四个出口全覆盖」——
   `no-key` / `bad-json` / SSE 直通 / 整包透传 四条里三条在线上根本取不到样本（要余额、要挂起）；
3. 本地用**假 fetch** 驱动真函数模块，四条出口各跑一次，还能把「头被摘掉」做成反向腿。
   线上版另留 `--live` 做补充取证，不进电池。

四条出口 = 该模块的全部 return 点（`src/functions/api/chat.js` 实测 4 处 Response）。
漏一条就等于回到 r57 修之前那种「只修看得见的出口」（[[fix-the-producer-covers-all-egress]]）。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FN = ROOT / "src" / "functions" / "api" / "chat.js"
DEPLOY_FN = ROOT / "deploy" / "functions" / "api" / "chat.js"

REQUIRED = {
    "content-security-policy": "default-src 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "cross-origin-opener-policy": "same-origin",
}
# SSE 那条要 no-transform（否则中间层会重编码事件流）+ 真事件流 content-type；
# 其余出口要 no-store（对话响应不该被缓存）。
STREAM_MUST = {"cache-control": "no-transform", "content-type": "text/event-stream"}
JSON_MUST = {"cache-control": "no-store"}

# 交给 node 的驱具：假 fetch + 四条出口各打一次，输出 JSON 到 stdout。
HARNESS = r"""
import(%(fnurl)s).then(async (mod) => {
  const out = [];
  const req = (body, ctype) => new Request("https://x/api/chat", {
    method: "POST",
    headers: { "content-type": ctype || "application/json" },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
  const hdrs = (r) => { const o = {}; for (const [k, v] of r.headers.entries()) o[k] = v; return o; };
  const call = async (name, env, request, fetchImpl) => {
    const prev = globalThis.fetch;
    if (fetchImpl) globalThis.fetch = fetchImpl;
    let r, err = null;
    try { r = await mod.onRequestPost({ request, env, params: {}, waitUntil() {}, ctx: {}, cf: {}, next() {} }); }
    catch (e) { err = String(e && e.message || e); }
    globalThis.fetch = prev;
    let body = null;
    try { body = await r.clone().text(); } catch (e) { body = "<unreadable>"; }
    out.push({ name, status: r ? r.status : null, headers: r ? hdrs(r) : {}, body, err });
  };
  const upJSON = () => async () => new Response(JSON.stringify({ id: "stub", choices: [] }), {
    status: 200, headers: { "content-type": "application/json" } });
  const upSSE = () => async () => new Response("data: {\"x\":1}\n\n", {
    status: 200, headers: { "content-type": "text/event-stream" } });
  const upErr = () => async () => new Response(JSON.stringify({ error: { message: "Insufficient Balance" } }), {
    status: 402, headers: { "content-type": "application/json" } });
  await call("no-key", {}, req({ messages: [] }), null);
  await call("bad-json", { DEEPSEEK_KEY: "stub-key" }, "{not json", upJSON());
  await call("sse", { DEEPSEEK_KEY: "stub-key" }, req({ messages: [], stream: true }), upSSE());
  await call("passthrough", { DEEPSEEK_KEY: "stub-key" }, req({ messages: [] }), upJSON());
  await call("upstream-error", { DEEPSEEK_KEY: "stub-key" }, req({ messages: [] }), upErr());
  await call("stream-fallback", { DEEPSEEK_KEY: "stub-key" },
             req({ messages: [], stream: true }), upErr());
  console.log(JSON.stringify(out));
});
"""


def probe(fn_path: Path):
    """在 node 里驱动真函数模块，返回逐出口实测；环境不满足时抛 RuntimeError。"""
    try:
        node = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=20)
    except Exception as exc:
        raise RuntimeError("node 不可调用: %s" % type(exc).__name__)
    if node.returncode != 0:
        raise RuntimeError("node --version rc=%s" % node.returncode)
    with tempfile.TemporaryDirectory() as td:
        # 夹具落临时目录（受管根禁临时产物）；被测模块按 file:// URL 引入，
        # 中文项目路径由 as_uri() 百分号编码 —— 直接拼字符串会在 node 侧解析失败。
        h = Path(td) / "harness.mjs"
        h.write_text(HARNESS % {"fnurl": json.dumps(fn_path.as_uri())}, encoding="utf-8")
        try:
            r = subprocess.run(["node", str(h)], capture_output=True, text=True,
                               timeout=90, cwd=str(ROOT))
        except Exception as exc:
            raise RuntimeError("node 驱具执行异常: %s" % type(exc).__name__)
    err = (r.stderr or "").strip()
    if r.returncode != 0:
        raise RuntimeError("node 驱具 rc=%s stderr=%s" % (r.returncode, err[:200]))
    try:
        return json.loads(r.stdout.strip())
    except Exception as exc:
        raise RuntimeError("驱具输出非 JSON（%s）: %s" % (type(exc).__name__, r.stdout[:200]))


def assess(exits, strip=None):
    """纯判定：逐出口断言安全头 + 契约形状。`strip` 供反向腿摘掉头。"""
    bad = []
    names = {e["name"] for e in exits}
    want_names = {"no-key", "bad-json", "sse", "passthrough", "upstream-error", "stream-fallback"}
    if want_names - names:
        return ["出口枚举不全：缺 %s（该模块的 return 点必须逐个测，r57 G3）"
                % sorted(want_names - names)]
    expect = {"no-key": 500, "bad-json": 400, "sse": 200, "passthrough": 200,
              "upstream-error": 402, "stream-fallback": 402}
    for e in exits:
        h = {k.lower(): v for k, v in (e.get("headers") or {}).items()}
        if strip and e["name"] == strip.split(":", 1)[0]:
            h = {k: v for k, v in h.items() if k != strip.split(":", 1)[1]}
        for k, v in REQUIRED.items():
            got = h.get(k)
            if not got:
                bad.append("%s 缺 %s" % (e["name"], k))
            elif v not in got:
                bad.append("%s 的 %s=%r 不含 %r" % (e["name"], k, got[:60], v))
        need = STREAM_MUST if e["name"] == "sse" else JSON_MUST
        for k, v in need.items():
            if v not in (h.get(k) or ""):
                bad.append("%s 的 %s=%r 应为 %r 类语义" % (e["name"], k, h.get(k), v))
        if e.get("err"):
            bad.append("%s 抛错: %s" % (e["name"], e["err"][:80]))
        if e.get("status") != expect[e["name"]]:
            bad.append("%s 状态码 %s ≠ 契约 %s（加头不得改形状，AC-OBS-08）"
                       % (e["name"], e.get("status"), expect[e["name"]]))
    body = next((e for e in exits if e["name"] == "no-key"), {})
    if "no-key" not in json.dumps(body.get("body") or "", ensure_ascii=False):
        bad.append("no-key 出口的错误体形状变了（契约要求 {\"error\":\"no-key\"}）: %r"
                   % str(body.get("body"))[:60])
    return bad


def run() -> int:
    if not FN.is_file():
        print("APIEGRESS-UNVERIFIED: 函数权威源不存在 -> %s" % FN.name)
        return 2
    try:
        exits = probe(FN)
    except RuntimeError as exc:
        print("APIEGRESS-UNVERIFIED: %s ⇒ 环境不满足不判绿（也不判红）" % exc)
        return 2
    bad = assess(exits)
    same = FN.is_file() and DEPLOY_FN.is_file() and FN.read_bytes() == DEPLOY_FN.read_bytes()
    if not same:
        bad.append("部署副本与权威源不一致：deploy/functions/api/chat.js 未被判据覆盖即漂移")
    for x in bad:
        print("  ✗ " + x)
    if bad:
        print("APIEGRESS-FAIL: %d 条（出口 %d 条实测）" % (len(bad), len(exits)))
        return 1
    codes = "/".join("%s=%s" % (e["name"], e["status"]) for e in exits)
    print("APIEGRESS-PASS: %d 条出口 5 类安全头齐、状态码逐条同契约、部署副本与权威源逐字节等（%s）"
          % (len(exits), codes))
    return 0


def selftest() -> int:
    """反向腿：证明「头被摘掉」与「出口少一条」都会红，而不是只跑正向。"""
    good = [{"name": n, "status": s, "headers": {
        "content-security-policy": "default-src 'none'", "x-content-type-options": "nosniff",
        "referrer-policy": "no-referrer", "cross-origin-opener-policy": "same-origin",
        "content-type": "text/event-stream; charset=utf-8" if n == "sse" else "application/json",
        "cache-control": "no-cache, no-transform" if n == "sse" else "no-store"},
        "body": '{"error":"no-key"}' if n == "no-key" else "{}", "err": None}
        for n, s in [("no-key", 500), ("bad-json", 400), ("sse", 200),
                     ("passthrough", 200), ("upstream-error", 402), ("stream-fallback", 402)]]
    bad = []
    if assess(good):
        bad.append("①正例被判红 ⇒ 判据有假阳性：%s" % assess(good))
    m1 = assess(good, strip="sse:content-security-policy")
    if not any("sse 缺 content-security-policy" in x for x in m1):
        bad.append("②摘掉 SSE 的 CSP 未翻红 ⇒ 判据恒绿")
    m2 = assess(good, strip="passthrough:cache-control")
    if not any("passthrough 的 cache-control" in x for x in m2):
        bad.append("③摘掉透传出口的 no-store 未翻红")
    m3 = assess([e for e in good if e["name"] != "bad-json"])
    if not any("出口枚举不全" in x for x in m3):
        bad.append("④少一条出口未被抓到（只测看得见的出口 = r57 前的状态）")
    m4 = assess([{**good[0], "status": 200}] + good[1:])
    if not any("状态码" in x for x in m4):
        bad.append("⑤状态码漂移未被抓到（加头顺手改契约）")
    m5 = assess([{**good[0], "body": "OK"}] + good[1:])
    if not any("错误体形状" in x for x in m5):
        bad.append("⑥错误体形状漂移未被抓到")
    m6 = assess([{**good[2], "headers": {**good[2]["headers"], "cache-control": "no-store"}}]
                + [e for e in good if e["name"] != "sse"])
    if not any("no-transform" in x for x in m6):
        bad.append("⑦SSE 出口给成 no-store 未被抓到（流被中间层重编码这条路要单独钉）")
    print("APIEGRESS-SELFTEST-%s（7 腿：正例 + 摘头×2 + 缺出口 + 状态码 + 错误体 + SSE 语义）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad)))
    for x in bad:
        print("  ✗ " + x)
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(run())
