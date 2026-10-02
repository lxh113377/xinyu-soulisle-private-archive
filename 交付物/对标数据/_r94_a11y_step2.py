# -*- coding: utf-8 -*-
"""r94 步骤②：把 a11y_check.main() 的「累加器初始化 + with sync_playwright() 整块」下移到 `_run_audit()`。

切点用 AST 定位：`viol_total = 0` 那条起，到 `bad = [n for n, ok, d in results ...]` 那条前止。
`results`（模块级）与 `check`（模块级）不需传参；post 段要用的 5 个量由返回值交回。
"""
import ast
from pathlib import Path

P = Path("_test/a11y_check.py")
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)
tree = ast.parse("".join(lines))
fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "main")

i_start = next(k for k, st in enumerate(fn.body)
               if isinstance(st, ast.Assign) and getattr(st.targets[0], "id", "") == "viol_total")
i_end = next(k for k, st in enumerate(fn.body)
             if isinstance(st, ast.Assign) and getattr(st.targets[0], "id", "") == "bad")
a, b = fn.body[i_start].lineno, fn.body[i_end - 1].end_lineno
seg = lines[a - 1:b]
print("搬移区间 %d..%d = %d 行" % (a, b, len(seg)))
assert seg[0].strip() == "viol_total = 0", seg[0]
assert seg[-1].strip().startswith("b.close()") or seg[-1].strip() != "", seg[-1]

DOC = ['    """r94：由 `main` 的「累加器初始化 + `with sync_playwright()` 整块」下移而来。\n',
       '    `results` 与 `check` 在模块级 ⇒ 块内断言照旧追加；post 段要用的 5 个量由返回值交回。\n',
       '    """\n']

new = ["def _run_audit(src, opts):\n"] + DOC + seg + [
    "    return viol_total, states_red, passes_min, inc, deltas\n", "\n", "\n"]
call = ["    viol_total, states_red, passes_min, inc, deltas = _run_audit(src, opts)\n"]

new_lines = lines[:a - 1] + call + lines[b:]
i_main = next(i for i, s in enumerate(new_lines) if s.startswith("def main("))
out = new_lines[:i_main] + new + new_lines[i_main:]
P.write_text("".join(out), encoding="utf-8")
print("written; lines=%d ｜ 新函数行数=%d" % (len(out), len(new) + len(seg) - 1))
