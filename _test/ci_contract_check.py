"""ci_contract_check.py — CI 全绿契约的**结构性**门（r95 立，常驻判据）。

要封口的缺陷族（一手，非推测）：本仓的「CI 全绿契约」装了钩子、装了 schema，唯独契约文件本身
**从未被 git 跟踪**，于是整条链路静默失灵：

  · `.git/hooks/pre-push`（greencheck 通用模板，2378B）在位，头注写着「找不到判据时**失败关闭**」；
  · `greencheck.py` 的硬规矩第 2 条：「契约必须被 git 跟踪，否则 runner 拒绝执行」；
  · 实测 `greencheck run --repo-dir .` → `[greencheck] UNKNOWN（契约未被 git 跟踪 ⇒ 拒绝执行）`；
  · 而 `greencheck.py` 的 main 对 UNKNOWN 走 `return 1 if verdict == "RED" else 0`
    ⇒ **UNKNOWN ⇒ rc=0 ⇒ 钩子打印「PASS: 契约内 blocking 检查全绿，放行推送」并 exit 0**。

即：门上写着"失败关闭"，实测是"恒放行"，而这两条都不抛异常、不打警告。这一族与本仓已修过的
「判据印 FAIL 却无非零退出路径」是同一个根：**"有门"与"门有牙"分家**（r78「有配置≠有门」的同族，
这次发生在自己身上）。r93 抓到 j2_chat_contract、r94 抓到 j4_memory_check，都是修例不修类；
本件是这个类的**第三只脚**，站在门里面。

判据（静态、零网络、零浏览器，且**不调用 greencheck run** —— 那会递归）：
  1) 契约文件存在，且被 `git ls-files` 跟踪（未跟踪 ⇒ 门恒放行，直接红）
  2) schema/repo/branch/refresh_days 四要素在位且类型正确（refresh_days 缺了就只剩代码常量里的保质期）
  3) `checks` 非空（空契约 = 零保护还像成功了，greencheck 自己也这么说）
  4) blocking 的 `name` 唯一（bootstrap 按 workflow step 名命名，一个 step 内多条命令必撞名 ——
     r95 实测前一份契约 4 条 checks 里就有 2 组同名）
  5) 每条 blocking 有 `cmd` / `timeout_s` / `cost_ms`>0 / `cost_source` ∈ {measured,assumed,ci-observed}
  6) `blocking_total_cost_ms` == 各条 cost_ms 之和（声明的总预算必须能被复算，否则"在预算内"不可核）
  7) blocking 合计 <= PRE_PUSH_BUDGET_MS（超了就等于每条都会被 defer，契约形同虚设）
  8) **接线自证**：每条 blocking 的脚本文件名必须出现在 `.github/workflows/*.yml` 或
     `_test/run_all_suites.py` 里 —— 契约列了但没人跑，与没列同价
  9) 每条 `deferred` 必须带非空 `reason`，且 `reason` 里必须点名承接面
     （承接面 = CI 作业名 / 电池 / 环境缺失；没有承接面的 defer 等于"这条没人管"）

为什么不用「跑一遍 greencheck run 看 verdict」当判据：契约第一条就是本件自己，跑它会无限递归。
所以本件只做**结构与接线**判定，运行时判定交给 greencheck 自己。
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / ".ci" / "contract.json"
WORKFLOWS = ROOT / ".github" / "workflows"
BATTERY = ROOT / "_test" / "run_all_suites.py"

PRE_PUSH_BUDGET_MS = 20000          # greencheck --blocking-budget-s 默认值
COST_SOURCES = ("measured", "assumed", "ci-observed")
# 「承接面」关键词：deferred 的理由必须回答"这条谁管"
CARRY_TOKENS = ("CI", "ci.yml", "workflow", "作业", "电池", "battery", "环境", "node", "Docker", "公网")


def _git(*args):
    """跑 git 并**显式 encoding**（本仓同族坑第三条：按路径匹配子进程输出必须控住编码/解码假设）。"""
    p = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=60)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def is_tracked(rel):
    rc, out, _ = _git("ls-files", "--error-unmatch", "--", rel)
    return rc == 0 and out.strip() != ""


def read_contract():
    """→ (数据, 错误串)。错误串非空即调用方必须判 UNVERIFIED，不得当绿。"""
    if not CONTRACT.is_file():
        return None, "契约文件不存在：%s" % CONTRACT
    try:
        return json.loads(CONTRACT.read_text(encoding="utf-8")), ""
    except (OSError, ValueError) as e:
        return None, "契约读不到/解析失败：%s" % str(e)[:80]


def script_of(cmd):
    """从契约命令里取**接线令牌**（.py/.js 取文件名；`python -m mod` 取模块名）。取不到返回 ''。

    为什么要有第二种形态：`python -m compileall -q _test` 是本仓 CI 里真实存在的一步，
    但它没有 `_test/xxx.py` 文件名。第一版只认文件形态 ⇒ 把这条合法 blocking 判成
    「无法验接线」。这类"尺比它自称的语义窄"的误报与假阳同源，同样要清掉。
    """
    m = re.search(r"[\\/]([\w.\-]+\.(?:py|js))", str(cmd))
    if m:
        return m.group(1)
    m = re.search(r"-m\s+([\w.\-]+)", str(cmd))
    return m.group(1) if m else ""


def wiring_surface():
    """→ (脚本名集合, 原文集合)。取数面全空即调用方判 UNVERIFIED。"""
    ci, bat, raw = set(), set(), []
    if WORKFLOWS.is_dir():
        for p in WORKFLOWS.rglob("*.yml"):
            t = p.read_text(encoding="utf-8", errors="replace")
            ci.update(re.findall(r"_test/[\w.\-]+\.(?:py|js)", t))
            raw.append(t)
    if BATTERY.is_file():
        t = BATTERY.read_text(encoding="utf-8", errors="replace")
        bat.update(re.findall(r"_test/[\w.\-]+\.(?:py|js)", t))
        raw.append(t)
    return ci, bat, raw


def evaluate(data, ci_scripts, bat_scripts, raw_text=()):
    """纯函数：契约 dict + 三个接线面 → 问题串列表（空列表 = 通过）。"""
    bad = []
    for key, typ in (("schema", str), ("repo", str), ("branch", str), ("refresh_days", int)):
        if not isinstance(data.get(key), typ) or data.get(key) in ("", 0):
            bad.append("契约缺要素或类型不对：%s（要求 %s，实际 %r）" % (key, typ.__name__, data.get(key)))

    checks = data.get("checks")
    if not isinstance(checks, list) or not checks:
        bad.append("checks 为空或不是数组 ⇒ 空契约 = 零保护还像成功了（greencheck run 会直接 UNKNOWN）")
        return bad
    blocking = [c for c in checks if c.get("blocking", True)]

    seen = {}
    for c in checks:
        nm = str(c.get("name") or "")
        if not nm:
            bad.append("有一条 check 没有 name（greencheck 用 name 定位日志与 --only，缺名不可用）")
            continue
        seen[nm] = seen.get(nm, 0) + 1
    for nm, k in sorted(seen.items()):
        if k > 1:
            bad.append("check 名重复 %d 次：%s（名字撞车 ⇒ 日志互相覆盖、--only 只能命中一条）" % (k, nm))

    # 接线面按**脚本名**归一（ci/bat 两面存的是 "_test/x.py"，契约 cmd 取出的是 "x.py"）。
    # ⚠️ 第一版写成 `any(s in x for x in (ci_scripts, bat_scripts))` —— 那是在两个 **set** 上迭代，
    # 做的是「s 是否是这两个 set 的成员」，恒 False ⇒ 14 条 blocking 全被误报「没人跑」。
    # 由 --selftest 的**正例腿**当场抓到（正例本该零问题却报 1 条）。真例：集合要先摊平成名字集合。
    known = {x.rsplit("/", 1)[-1] for x in (set(ci_scripts) | set(bat_scripts))}
    raw_join = "\n".join(raw_text)
    total = 0
    for c in blocking:
        nm = str(c.get("name") or "<无名>")
        if not str(c.get("cmd") or "").strip():
            bad.append("%s：cmd 为空" % nm)
        if not isinstance(c.get("timeout_s"), int):
            bad.append("%s：timeout_s 缺失或非整数（greencheck 会回落默认常量，超长任务将被截断）" % nm)
        cs = c.get("cost_source")
        if cs not in COST_SOURCES:
            bad.append("%s：cost_source=%r 不在 %s 内（成本来源不可核 ⇒ 预算声明是空话）" % (nm, cs, COST_SOURCES))
        cm = c.get("cost_ms")
        if not isinstance(cm, int) or cm <= 0:
            bad.append("%s：cost_ms 缺失或非正（%r）" % (nm, cm))
            cm = 0
        total += cm
        s = script_of(c.get("cmd"))
        if not s:
            bad.append("%s：cmd 里取不到 _test 脚本名或 -m 模块名（%r）⇒ 无法验接线" % (nm, c.get("cmd")))
        elif s.endswith((".py", ".js")):
            if s not in known:
                bad.append("%s：脚本 %s 在 CI workflow 与电池里都找不到执行位 ⇒ 列了但没人跑" % (nm, s))
        elif s not in raw_join:
            bad.append("%s：模块 %s 在 CI workflow 与电池的正文里都找不到 ⇒ 列了但没人跑" % (nm, s))

    declared = data.get("blocking_total_cost_ms")
    if declared != total:
        bad.append("blocking_total_cost_ms=%r 与各条 cost_ms 之和 %d 不等 ⇒ 预算声明不可复算"
                   % (declared, total))
    if total > PRE_PUSH_BUDGET_MS:
        bad.append("blocking 合计 %dms > pre-push 预算 %dms ⇒ 超预算的条目会被 defer，契约形同虚设"
                   % (total, PRE_PUSH_BUDGET_MS))

    for d in data.get("deferred") or []:
        nm = str(d.get("name") or "<无名>")
        why = str(d.get("reason") or "").strip()
        if not why:
            bad.append("deferred[%s]：无 reason ⇒ 这条判红时没人管（'超预算'不等于'有人承接'）" % nm)
        elif not any(t in why for t in CARRY_TOKENS):
            bad.append("deferred[%s]：reason 未点名承接面（须含 %s 之一）｜现为「%s」"
                       % (nm, "/".join(CARRY_TOKENS), why[:60]))
    return bad


# ── 自检：正例 / 反例 / 变异体 / 结构腿（缺一腿 = 本件没资格当判据）────────────
def _ok_contract():
    return {
        "schema": "fenjue-ci-green-contract-v1", "repo": "o/n", "branch": "main",
        "refresh_days": 7, "blocking_total_cost_ms": 100,
        "checks": [{"name": "a", "cmd": "python _test/x.py", "timeout_s": 60,
                    "blocking": True, "cost_ms": 100, "cost_source": "measured"}],
        "deferred": [{"name": "d", "cmd": "mvn verify", "reason": "环境缺失，由 CI java-build 作业承接"}],
    }


def selftest():
    CI_FACE = {"_test/x.py", "_test/y.py"}
    BAT_FACE = {"_test/z.py"}
    RAW_FACE = ("python -m compileall -q _test",)
    cases = []

    def run(label, data, ci=CI_FACE, bat=BAT_FACE, raw=RAW_FACE):
        cases.append((label, len(evaluate(data, ci, bat, raw)), 0))

    def run_red(label, data, needle, ci=CI_FACE, bat=BAT_FACE, raw=RAW_FACE):
        bad = evaluate(data, ci, bat, raw)
        cases.append((label, 1 if any(needle in b for b in bad) else 0, 1))

    # 正例
    run("正例 完整契约零问题", _ok_contract())
    run("正例 无 deferred 段（可选）", {**_ok_contract(), "deferred": []})
    run("正例 `python -m 模块` 形态能验接线（第一版尺比语义窄，会误报这条）",
        {**_ok_contract(), "blocking_total_cost_ms": 100,
         "checks": [{"name": "a", "cmd": "python -m compileall -q _test", "timeout_s": 60,
                     "blocking": True, "cost_ms": 100, "cost_source": "measured"}]})
    # 反例（逐条注入一手形态）
    run_red("反例A blocking 合计与声明不等", {**_ok_contract(), "blocking_total_cost_ms": 999}, "不可复算")
    run_red("反例B 超 pre-push 预算", {**_ok_contract(), "blocking_total_cost_ms": 99999,
                                      "checks": [{**_ok_contract()["checks"][0], "cost_ms": 99999}]},
            "形同虚设")
    run_red("反例C check 名重复", {**_ok_contract(), "checks": _ok_contract()["checks"] * 2}, "重复")
    run_red("反例D 契约缺 refresh_days", {k: v for k, v in _ok_contract().items() if k != "refresh_days"}, "缺要素")
    run_red("反例E cost_source 不在枚举", {**_ok_contract(),
             "checks": [{**_ok_contract()["checks"][0], "cost_source": "guess"}]}, "cost_source")
    run_red("反例F 脚本无执行位（契约列了但没人跑）", {**_ok_contract(),
             "checks": [{**_ok_contract()["checks"][0], "name": "a", "cmd": "python _test/orphan.py"}]},
            "没人跑")
    run_red("反例G deferred 无 reason", {**_ok_contract(), "deferred": [{"name": "d", "cmd": "mvn verify"}]},
            "没人管")
    run_red("反例H deferred 有 reason 但未点名承接面", {**_ok_contract(),
             "deferred": [{"name": "d", "cmd": "mvn verify", "reason": "太慢了"}]}, "承接面")
    run_red("反例I `-m` 模块在 CI 正文里也找不到", {**_ok_contract(),
             "checks": [{**_ok_contract()["checks"][0], "cmd": "python -m nonexistent_mod"}]}, "没人跑")
    # 结构腿：checks 为空必须单独成红，不许静默通过
    run_red("结构腿 checks 空数组即红（空契约不是零问题）", {**_ok_contract(), "checks": []}, "零保护")
    # 变异体：**填上**执行位后同一条必须不再报「没人跑」（证明该识别作用在被测对象上，
    #   而不是恒红 —— 第一版把 `any(s in x for x in (集合, 集合))` 写成了对容器做成员判定，
    #   恒 False，于是 14 条合法 blocking 全被误报；只有正例腿能抓到它，变异体腿抓不到）。
    mut = evaluate({**_ok_contract(),
                    "checks": [{**_ok_contract()["checks"][0], "cmd": "python _test/orphan.py"}]},
                   {"_test/orphan.py"}, set(), RAW_FACE)
    cases.append(("变异体 给 orphan 补上执行位后『没人跑』消失（证明非恒红）",
                  0 if any("没人跑" in b for b in mut) else 1, 1))
    # 变异体：脚本名取不到时必须点名，不许静默跳过
    run_red("变异体 cmd 既无脚本也无 -m ⇒ 点名而非跳过", {**_ok_contract(),
             "checks": [{**_ok_contract()["checks"][0], "cmd": "echo hi"}]}, "无法验接线")

    bad = [(n, g, w) for n, g, w in cases if g != w]
    for n, g, w in bad:
        print("  用例不符: %s ｜ got=%d want=%d" % (n, g, w))
    print("CI-CONTRACT-SELFTEST-%s（%d/%d 条）"
          % ("PASS" if not bad else "FAIL", len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--contract", default=str(CONTRACT))
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    data, err = read_contract()
    if err:
        print("CI-CONTRACT-UNVERIFIED: %s" % err)
        return 2
    ci_scripts, bat_scripts, raw_text = wiring_surface()
    if not ci_scripts and not bat_scripts and not raw_text:
        print("CI-CONTRACT-UNVERIFIED: 接线面为空（.github/workflows/*.yml 与 run_all_suites.py 都读不到脚本名）"
              "⇒ 没测到，不判绿")
        return 2

    tracked = is_tracked(".ci/contract.json")
    problems = evaluate(data, ci_scripts, bat_scripts, raw_text)
    if not tracked:
        problems.insert(0, "🔴 契约未被 git 跟踪 ⇒ greencheck run 恒回 UNKNOWN ⇒ pre-push 钩子恒放行"
                            "（门装在位但不咬人；修：git add .ci/contract.json）")
    blocking = [c for c in data.get("checks") or [] if c.get("blocking", True)]
    print("CI-CONTRACT-%s: tracked=%s checks=%d(blocking) deferred=%d ci_scripts=%d battery_scripts=%d "
          "budget=%dms/%dms 问题=%d"
          % ("FAIL" if problems else "PASS", tracked, len(blocking),
             len(data.get("deferred") or []), len(ci_scripts), len(bat_scripts),
             sum(c.get("cost_ms") or 0 for c in blocking), PRE_PUSH_BUDGET_MS, len(problems)))
    for p in problems:
        print("  !! %s" % p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())