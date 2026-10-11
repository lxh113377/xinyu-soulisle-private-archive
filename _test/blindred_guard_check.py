# -*- coding: utf-8 -*-
"""BLIND-RED 常驻棘轮（r112）——「判据崩了却不打结论行」这一族的门禁。

为什么要有这一件（而不是只修那 4 个脚本）：
  r105 把「rc≠0 但零结论行」记为 BLIND-RED，当时 6 条；本轮修了 4 台仪器。
  但**单点修复必然再犯**——同族第二次出现了（r96 判过 peers 的假门，r105 长到自己身上）。
  修文件只消除今天的 4 条，改判据的人明天还会写出第 5 条。所以必须有一件常驻判据，
  用 AST 清点「裸抛栈点」，让这一族在**写出来的那一刻**就被抓住，而不是等整跑。

什么叫裸抛栈点（本件的取数面）：
  ① 不在任何 try 保护范围内的 `assert` —— 失败即 AssertionError，脚本在印结论行之前死掉；
  ② 不在任何 try 保护范围内的 `page.wait_for_function/selector(...)` —— playwright 超时
     抛 TimeoutError，同样是零结论行。
  两者的共同后果：电池只看到 rc≠0，与「环境未验」在账面上不可分 ⇒ 真缺陷被仪器自己的崩溃盖住。

取数范围：只扫 `run_all_suites.py` 的 SUITES 名册里**真实在册**的脚本（分母现读，不写死）。
  不在册的脚本（探针/一次性工具）不进分母 —— 它们不参与电池记账，判红会制造噪声。

用法：
  python _test/blindred_guard_check.py              # 清点 + 判红
  python _test/blindred_guard_check.py --selftest    # 变异腿：注入裸 assert 必须被抓到
  python _test/blindred_guard_check.py --machine     # 打印逐文件明细

判据语义（与 check_instrument.py 成套）：
  BLINDRED-GUARD-PASS  裸抛栈点 ≤ 基线 ⇒ 绿（并提示是否已可下调基线）
  BLINDRED-GUARD-RED   裸抛栈点 > 基线 ⇒ 判红，点名到 文件:行，并给出改法（不是要求删断言）
  rc=2                 名册取不到/环境不满足 ⇒ 未验，不得当绿

**基线只降不升**（与 E2 / C1 同族棘轮同形态）：
  基线 = 21（r112 首扫实测；立基线前是 23 —— 本轮先把 BLIND-RED 名单上的 4 台仪器
  j4_memory / browser_check / pixel_dual / lightshow 修到零裸点，再从 23 下调到 21）。
  余下 21 处分布在**其他**在册套件，本轮不动（改动面会撞并行会话），按「不许新增」管住：
  下一轮每修一处，就把默认基线同步下调一处，直到归零。
"""
import ast
import io
import os
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNNER = HERE / "run_all_suites.py"

WAIT_ATTRS = ("wait_for_function", "wait_for_selector")
# 只降不升的棘轮基线。沿革（每行都是实测后下调，不是拍的）：
#   r112 首扫 23 → 修完 4 台 BLIND-RED 仪器（j4/browser/pixel_dual/lightshow）21
#   → r113 给其余 8 件装 install_excepthook 进程级兜底 **0**（已兜底 20 处仍在册，但不判红）
# 口径说明：判红看的是「**未兜底**裸点」——装了 install_excepthook 或整段在 try 内的
# 裸点不会造成零结论行，故不计入。**不得因新增代码而上调基线。**
BASELINE_DEFAULT = 0
SELFTEST_SRC = """
import sys
def f():
    pass
assert 1 == 2, "这是一条**故意**的裸断言（selftest 注入，必须被抓到）"
page.wait_for_function("() => true", timeout=10)
try:
    assert True
except AssertionError:
    sys.exit(1)
"""


def roster():
    """从 SUITES 名册取在册脚本路径（分母现读）。"""
    if not RUNNER.exists():
        return [], "run_all_suites.py 不存在"
    src = RUNNER.read_text(encoding="utf-8", errors="replace")
    hits = re.findall(r'"(_test[/\\][A-Za-z0-9_\-.]+\.py)"', src)
    out, seen = [], set()
    for h in hits:
        p = ROOT / h.replace("/", os.sep)
        if p.exists() and str(p) not in seen:
            seen.add(str(p))
            out.append(p)
    return out, ("" if out else "名册里取不到任何在册脚本")


def protected_lines(tree):
    """所有被 try（含 handler/else/finally）包住的行号。"""
    prot = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        parts = list(node.body) + list(node.orelse) + list(node.finalbody)
        for h in node.handlers:
            parts += list(h.body)
        stack = list(parts)
        while stack:
            st = stack.pop()
            prot.add(getattr(st, "lineno", -1))
            stack.extend(ast.iter_child_nodes(st))
    return prot


def scan_source(src, filename="<src>"):
    """返回 ([(kind, lineno, snippet)], hooked)。

    hooked = 该脚本是否装了 `install_excepthook` —— 装了就**整份脚本**都由进程级兜底覆盖，
    其裸点不会造成「零结论行」，故不计入判红（本件真正管的是结论行有没有，不是 assert 写没写）。
    """
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [("syntax-error", e.lineno or 0, str(e))], False
    prot = protected_lines(tree)
    out = []
    hooked = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            nm = getattr(f, "id", None) or getattr(f, "attr", None)
            if nm == "install_excepthook":
                hooked = True
    for node in ast.walk(tree):
        ln = getattr(node, "lineno", None)
        if ln is None or ln in prot:
            continue
        if isinstance(node, ast.Assert):
            out.append(("assert", ln, (src.splitlines()[ln - 1].strip() if ln <= len(src.splitlines()) else "")))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in WAIT_ATTRS:
            out.append(("wait", ln, node.func.attr))
    return out, hooked


def main(argv):
    machine = "--machine" in argv
    selftest = "--selftest" in argv
    baseline = BASELINE_DEFAULT
    for i, a in enumerate(argv):
        if a == "--baseline" and i + 1 < len(argv):
            try:
                baseline = int(argv[i + 1])
            except ValueError:
                pass

    if selftest:
        got, hooked0 = scan_source(SELFTEST_SRC, "selftest")
        kinds = {k for k, _, _ in got}
        ok = ("assert" in kinds) and ("wait" in kinds) and (not hooked0)
        # 变异 2：整段包进 try 后必须**抓不到**（证明取数面真认 try，不是无脑计数）
        wrapped = "try:\n" + "\n".join("    " + l for l in SELFTEST_SRC.splitlines() if l.strip()) \
                  + "\nexcept Exception:\n    pass\n"
        got2, _ = scan_source(wrapped, "selftest-wrapped")
        ok2 = not got2
        # 变异 3：装了 install_excepthook 的脚本，裸点仍在但必须被判为「已兜底」（hooked=True）
        _, hooked3 = scan_source("from check_instrument import install_excepthook\n"
                                "install_excepthook('X')\n" + SELFTEST_SRC, "selftest-hooked")
        ok3 = hooked3
        print("SELFTEST：注入裸 assert/wait → 抓到 %d 处（%s）；hooked=%s（应为 False）"
              % (len(got), sorted(kinds), hooked0))
        print("SELFTEST：整体包 try 后 → 抓到 %d 处（应为 0）" % len(got2))
        print("SELFTEST：装 install_excepthook 后 → hooked=%s（应为 True ⇒ 不计入判红）" % hooked3)
        if ok and ok2 and ok3:
            print("BLINDRED-GUARD-SELFTEST-PASS：三向变异均成立（判据非恒真）")
            return 0
        print("BLINDRED-GUARD-SELFTEST-RED：变异腿不成立 ⇒ 本件自身失效")
        return 1

    files, err = roster()
    if err:
        print("BLINDRED-GUARD-UNVERIFIED %s" % err)
        print("   处置：本件无法取数（rc=2），不得记为绿。")
        return 2

    total = 0       # 未兜底（判红口径）
    covered = 0     # 已兜底（装了 install_excepthook 或整段在 try 内）
    offenders = []
    for p in files:
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        hits, hooked = scan_source(src, str(p))
        rel = os.path.relpath(str(p), str(ROOT)).replace("\\", "/")
        if machine:
            print("  %-46s 裸点=%d %s" % (rel, len(hits), "(已兜底)" if hooked else "(未兜底)"))
        if hits and hooked:
            covered += len(hits)
        elif hits:
            total += len(hits)
            for kind, ln, snip in hits[:4]:
                offenders.append("%s:%d (%s) %s" % (rel, ln, kind, snip[:60]))

    if total <= baseline:
        tail = ""
        if total < baseline:
            tail = "（已低于基线 %d ⇒ 请把 BASELINE_DEFAULT 下调到 %d，棘轮只降不升）" % (baseline, total)
        print("BLINDRED-GUARD-PASS 未兜底裸点=%d ≤ 基线 %d（已兜底 %d 处｜在册 %d 件，取数=AST，"
              "区分 try 内外与 install_excepthook）%s" % (total, baseline, covered, len(files), tail))
        return 0

    print("BLINDRED-GUARD-RED 未兜底裸点=%d > 基线 %d（已兜底 %d 处｜在册 %d 件）⇒ 这些断言/等待失败时脚本会在印结论行之前死掉，"
          "电池只看到 rc≠0，与『环境未验』不可分：" % (total, baseline, covered, len(files)))
    for o in offenders[:14]:
        print("   · %s" % o)
    if len(offenders) > 14:
        print("   … 另有 %d 处（--machine 看全量）" % (len(offenders) - 14))
    print("   改法：把断言串包进 try/except AssertionError → instrument_red(NAME, 原因含读数)；"
          "wait 一律换 wait_done(...)（见 _test/check_instrument.py）。")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
