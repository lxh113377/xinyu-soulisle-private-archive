"""verdict_exit_parity_check.py — 门面结论与退出码奇偶对账（r94 立，候选常驻判据）。

要封口的缺陷族（本仓已发生两次）：套件把结论印成 `XXX-FAIL` 却没有任何非零退出路径，
而电池（`run_all_suites.py`）是**按 rc 记账**的 ⇒ 判据「报红而记绿」。
  · r93 一手：`j2_chat_contract.py` 印 `J2-CONTRACT-FAIL` 而 rc=0（当时只修了那一件）。
  · r94 一手：本件首跑扫 `_test/*.py` 89 个套件，仍抓到 1 处 —— `j4_memory_check.py`
    （全文 assert=0 / raise=0 / sys.exit=0，末行 `print("J4-MEMORY-PASS" if ok else "J4-MEMORY-FAIL")`
    之后无退出动作）。`j4_memory_check` 是 **AC-OBS-10（情绪记忆真落库）** 的验收判据。
  ⇒ 教训：修例不修类，同一族必然复发（对齐记忆 *Fix the class, not the case*）。

判据（静态、零网络、零浏览器，故可进电池任意档）：
  某脚本同时满足三条 ⇒ DEFECT
    1) 存在 `print(...FAIL|-RED|判红|：红...)` 形态的**门面结论行**（它会成为电池取用的最后一行）；
    2) 全文无 `assert`、无 `raise`（含 `raise SystemExit`）；
    3) 无任何可产生非零退出的语句（`sys.exit`/`exit(...)`/`os._exit`/`parser.exit` 带参）。
  只有 assert 没有显式退出的 ⇒ OK-exception（合法但脆：靠未捕获异常转 rc=1，不判红）；
  不印 FAIL 门面行的 ⇒ N/A（失败即 traceback，rc 天然非零）。

为什么必须含 OK-exception / N/A 两档（否则这把尺会咬错人）：
  `browser_check`/`pixel_dual_check`/`lightshow_check`/`online_check`/`public_check` 五个纯 `assert` 型
  套件在本件第一版（只认 sys.exit）下被判 DEFECT —— **假阳 5 处**。假阳的后果不是噪音，
  是逼读者去给本来就正确的判据加 sys.exit（改了个没坏的东西），或直接放宽判据。
"""
import argparse
import ast
import re
import sys
from pathlib import Path

WRAP_RE = re.compile(r"sys\.exit\(|os\._exit\(|\bexit\(\s*(?:1|rc|code|bad|ret|n_|len\(|not\b)"
                     r"|parser\.exit\(|argparse.*\.exit\(")
FAIL_PRINT_RE = re.compile(r"print\([^)\n]*(?:FAIL|-RED|判红|：红)")


def analyze_text(src):
    """纯函数：源码 → (桶名, 原因)。桶 ∈ DEFECT / OK-explicit / OK-exception / N/A / SYNTAX。"""
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return "SYNTAX", "SyntaxError@%s" % e.lineno
    has_assert = any(isinstance(n, ast.Assert) for n in ast.walk(tree))
    has_raise = any(isinstance(n, ast.Raise) for n in ast.walk(tree))
    has_wrap = bool(WRAP_RE.search(src))
    prints_fail = bool(FAIL_PRINT_RE.search(src))
    if not prints_fail:
        return "N/A", "无 FAIL 门面结论行"
    if has_wrap:
        return "OK-explicit", "有显式退出路径"
    if has_assert or has_raise:
        return "OK-exception", "靠未捕获 assert/raise 转 rc=1"
    return "DEFECT", "印 FAIL 门面行，但无 assert/raise/sys.exit ⇒ rc 恒 0"


def scan_dir(root):
    out = {}
    for p in sorted(Path(root).glob("*.py")):
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            out[p.name] = ("SYNTAX", "读失败:%s" % str(e)[:40])
            continue
        out[p.name] = analyze_text(src)
    return out


# ── 自检：正向 / 反例 / 变异体三腿（缺一腿 = 本件没资格当判据）────────────────
GOOD_EXPLICIT = '''
import sys
ok = check()
print("X-PASS" if ok else "X-FAIL")
sys.exit(0 if ok else 1)
'''
GOOD_ASSERT = '''
import json
def f(x):
    return json.loads(x)
bad = []
assert f("1") == 1
print("X-PASS" if not bad else "X-FAIL: %s" % bad)
'''
BAD_SHAPE = '''
ok = True
if bad_in:
    ok = False
print("J4-MEMORY-PASS" if ok else "J4-MEMORY-FAIL")
'''
BAD_SHAPE_RAISE = '''
ok = True
print("A-PASS" if ok else "A-FAIL")
raise RuntimeError("boom")          # 有 raise ⇒ 进程必然非零退出，不该判红
'''
NO_VERDICT_LINE = '''
def add(a, b):
    return a + b
print("value", add(1, 2))
'''
# 已知软面（**故意不判红**，把边界钉成用例而不是留给下一个人重新发现）：
# assert 存在但不在 FAIL 分支上 ⇒ 静态无法证「那条分支会转 rc≠0」，本件只作趋势读数，不作终审。
SOFT_SPOT = '''
import json
data = json.loads("{}")
if data == {}:
    print("Y-FAIL: 空对象")
assert data is not None
'''

FIXED = GOOD_EXPLICIT          # BAD_SHAPE 修好后的样子（补 sys.exit）


def selftest():
    cases = []
    # 正例：三种合法形态都不得判红
    cases.append(("正例 显式 sys.exit 不判红", analyze_text(GOOD_EXPLICIT)[0], "OK-explicit"))
    cases.append(("正例 纯 assert 型不判红（第一版假阳 5 处的封口）",
                  analyze_text(GOOD_ASSERT)[0], "OK-exception"))
    cases.append(("正例 有 raise 不判红", analyze_text(BAD_SHAPE_RAISE)[0], "OK-exception"))
    cases.append(("正例 无门面行不判红", analyze_text(NO_VERDICT_LINE)[0], "N/A"))
    cases.append(("边界腿 软面钉死：assert 不在 FAIL 分支 ⇒ 归 OK-exception 不判红（趋势读数非终审）",
                  analyze_text(SOFT_SPOT)[0], "OK-exception"))
    # 反例：注入本仓一手形态，必须判红
    cases.append(("反例 印 FAIL 无退出 ⇒ DEFECT", analyze_text(BAD_SHAPE)[0], "DEFECT"))
    cases.append(("反例 同形态修好 ⇒ 转绿", analyze_text(FIXED)[0], "OK-explicit"))
    # 变异体 A：摘掉门面行识别 ⇒ 上面的反例必须翻判（证明它作用在被检对象上）
    global FAIL_PRINT_RE, WRAP_RE
    keep = FAIL_PRINT_RE
    FAIL_PRINT_RE = re.compile(r"(?!x)x")            # 永不匹配
    mut_a = analyze_text(BAD_SHAPE)[0]
    FAIL_PRINT_RE = keep
    cases.append(("变异体A 摘掉门面行识别后反例翻判（不得仍报 DEFECT）", mut_a, "N/A"))
    # 变异体 B：摘掉退出路径识别 ⇒ 合法件会被误判红（证明这条识别真在挡假阳）
    keep2 = WRAP_RE
    WRAP_RE = re.compile(r"(?!x)x")
    mut_b = analyze_text(GOOD_EXPLICIT)[0]
    WRAP_RE = keep2
    cases.append(("变异体B 摘掉退出路径识别后正例翻红（证明假阳防线在位）", mut_b, "DEFECT"))
    # 结构腿：坏语法不得静默漏过
    cases.append(("结构腿 语法错单独成档不判绿", analyze_text("def (:\n")[0], "SYNTAX"))

    bad = [(n, got, want) for n, got, want in cases if got != want]
    for n, got, want in bad:
        print("  用例不符: %s ｜ got=%s want=%s" % (n, got, want))
    print("VERDICT-EXIT-PARITY-SELFTEST-%s（%d/%d 条）"
          % ("PASS" if not bad else "FAIL", len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="_test")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    res = scan_dir(a.root)
    if not res:
        # 零命中不得当通过：取数面为空 = 没测（对齐 R247）
        print("VERDICT-EXIT-PARITY-UNVERIFIED: 取数面 %s 下 0 个 .py，判未验不判绿" % a.root)
        return 2
    buckets = {}
    for name, (kind, why) in res.items():
        buckets.setdefault(kind, []).append((name, why))
    defects = buckets.get("DEFECT", []) + buckets.get("SYNTAX", [])
    n = len(res)
    print("VERDICT-EXIT-PARITY-%s: 取数面=%s/*.py 套件=%d defect=%d ok_explicit=%d "
          "ok_exception=%d na=%d syntax=%d"
          % ("FAIL" if defects else "PASS", a.root, n, len(buckets.get("DEFECT", [])),
             len(buckets.get("OK-explicit", [])), len(buckets.get("OK-exception", [])),
             len(buckets.get("N/A", [])), len(buckets.get("SYNTAX", []))))
    for name, why in sorted(buckets.get("DEFECT", [])):
        print("  !! %-38s %s" % (name, why))
    for name, why in sorted(buckets.get("SYNTAX", [])):
        print("  ~~ %-38s %s" % (name, why))
    return 1 if defects else 0


if __name__ == "__main__":
    sys.exit(main())
