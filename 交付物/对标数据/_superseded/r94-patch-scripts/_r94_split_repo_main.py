# -*- coding: utf-8 -*-
"""r94 一次性拆分：`repo_config_check.main()`（171 行）拆成三段。

前提（动手前查证）：`check()` 在模块级第 84 行、`results` 在模块级第 81 行 ⇒
各段往 `results` 追加不需要传参，这是行为等价的前提。

⚠️ 上一版按**行号**切，正好切在 G13 那条多行 check 的中间 ⇒ SyntaxError。
本版改用 **AST 定位语句起点**（`a.online` 那条 / `fails = ...` 那条），不在行号上下注。
"""
import ast
from pathlib import Path

P = Path("_test/repo_config_check.py")
src = P.read_text(encoding="utf-8")
lines = src.splitlines(keepends=True)
tree = ast.parse(src)
fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "main")

k1 = next(st.lineno for st in fn.body if "a.online" in ast.unparse(st))
k2 = next(st.lineno for st in fn.body
          if isinstance(st, ast.Assign) and getattr(st.targets[0], "id", "") == "fails")
start = fn.body[0].lineno
end = fn.body[-1].end_lineno
print("main %d..%d ｜ 切点 k1=%d (a.online) k2=%d (fails)" % (start, end, k1, k2))

seg1 = lines[start - 1:k1 - 1]
seg2 = lines[k1 - 1:k2 - 1]
seg3 = lines[k2 - 1:end]
print("seg1=%d 行, seg2=%d 行, seg3=%d 行" % (len(seg1), len(seg2), len(seg3)))
assert seg1[0].lstrip().startswith("ap = argparse"), seg1[0]
assert seg2[0].lstrip().startswith("if a.online"), seg2[0]
assert seg3[-1].strip().startswith("return 1 if fails else 0"), seg3[-1]

new = []
new.append("def _cfg_head():\n")
new.append('    """r94：main() 的 argparse + 环境门（原 main 171 行 > loc_guard 的 150 行门）。\n')
new.append("\n")
new.append("    `check()`（第 84 行）与 `results`（第 81 行）都在模块级 ⇒ 各段追加无需传参。\n")
new.append('    """\n')
new.extend(seg1)
new.append("    return a\n")
new.append("\n")
new.append("\n")
new.append("def _cfg_body(a):\n")
new.append('    """r94：main() 的在线通道 + G6/G7/G8/G11/G10/G9（原样搬，判据口径零改写）。"""\n')
new.extend(seg2)
new.append("\n")
new.append("\n")
new.append("def _cfg_report(results):\n")
new.append('    """r94：main() 的收尾统计与退出码（原样搬）。"""\n')
new.extend(seg3)
new.append("\n")
new.append("\n")
new.append("def main():\n")
new.append('    """r94：只留调度——三段分别下移到 `_cfg_head` / `_cfg_body` / `_cfg_report`。\n')
new.append("\n")
new.append("    调用序与原来逐语句一致 ⇒ 判据号、计数与退出码都不变（`REPO-CONFIG-PASS` 的\n")
new.append('    「实跑 N 项」是验真点）。切点由 AST 定位，不靠行号。\n')
new.append('    """\n')
new.append("    a = _cfg_head()\n")
new.append("    if a.selftest:\n")
new.append("        sys.exit(selftest())\n")
new.append("    _cfg_body(a)\n")
new.append("    return _cfg_report(results)\n")
new.append("\n")

out = lines[:fn.lineno - 1] + new + lines[end:]
P.write_text("".join(out), encoding="utf-8")
print("written; lines=%d" % len(out))
