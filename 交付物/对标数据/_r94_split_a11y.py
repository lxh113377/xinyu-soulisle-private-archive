# -*- coding: utf-8 -*-
"""r94 一次性搬移：`a11y_check.main()`（208 行）拆出 `_run_audit()`。

两步：
  ① 把键盘探针的 JS 字符串（kb = pg.evaluate(「三引号包住的那种」)）提到模块级 `_JS_KB`；
  ② 把「累加器初始化 + `with sync_playwright()` 整块」下移到 `_run_audit(src, opts)`，
     由它返回 post 段要用的 5 个量（viol_total/states_red/passes_min/inc/deltas）。

切点用 AST 定位语句（`viol_total = 0` 起、`bad = [... results ...]` 前止），不按行号。
搬移前已查证：`results`（第 69 行）与 `check`（第 72 行）在模块级 ⇒ 块内往 results 追加不需传参。
"""
import ast
from pathlib import Path

P = Path("_test/a11y_check.py")
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)

# ---------- ① 提 JS ----------
i0 = next(i for i, s in enumerate(lines) if 'kb = pg.evaluate("""' in s)
i1 = next(i for i in range(i0, len(lines)) if lines[i].strip() == '}""")')
js = []
for s in lines[i0:i1 + 1]:
    t = s.split('"""', 1)[1] if '"""' in s else s
    if t.rstrip().endswith('}""")'):
        t = t.rstrip()[:-len('}""")')]
    js.append(t.rstrip("\n"))
js_text = "\n".join(js)

i_main = next(i for i, s in enumerate(lines) if s.startswith("def main("))
const = ['# r94：键盘可达性探针的浏览器端脚本提到模块级（原在 `main` 内占 15 行，是该函数据\n',
         '# loc_guard 函数长门超标的原因之一）。搬的是**字符串常量**，无变量捕获，行为不变。\n',
         '_JS_KB = """' + js_text + '"""\n',
         '\n',
         '\n']

# ---------- ② AST 定位搬移区间（注意：要先做 ①，AST 才能反映新行号） ----------
tmp = lines[:i0] + ['        kb = pg.evaluate(_JS_KB)\n'] + lines[i1 + 1:]
src2 = "".join(tmp[:i_main] + const + tmp[i_main:])
tree = ast.parse(src2)
fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "main")
i_start = next(k for k, st in enumerate(fn.body)
               if isinstance(st, ast.Assign) and getattr(st.targets[0], "id", "") == "viol_total")
i_end = next(k for k, st in enumerate(fn.body)
             if isinstance(st, ast.Assign) and getattr(st.targets[0], "id", "") == "bad")
seg = fn.body[i_start:i_end]
a_start, a_end = seg[0].lineno, seg[-1].end_lineno
print("搬移区间 %d..%d（%d 条语句，%d 行）" % (a_start, a_end, len(seg), a_end - a_start + 1))
assert a_end - a_start + 1 <= 150, "搬移后仍超 150 行，需再想别的切法"

seg_lines = tmp[a_start - 1:a_end]
new = []
new.append("def _run_audit(src, opts):\n")
new.append('    """r94：由 `main` 的「累加器初始化 + `with sync_playwright()` 整块」下移而来。\n')
new.append("\n")
new.append("    `results` 与 `check` 在模块级 ⇒ 块内断言照旧追加，无需传参；本函数只把 post 段\n")
new.append("    要用的 5 个量交回去。`src`/`opts` 显式入参（不靠闭包捕获）。\n")
new.append('    """\n')
new.extend(seg_lines)
new.append("    return viol_total, states_red, passes_min, inc, deltas\n")
new.append("\n")
new.append("\n")

call = "    viol_total, states_red, passes_min, inc, deltas = _run_audit(src, opts)\n"
out = tmp[:a_start - 1] + [call] + tmp[a_end:]
# 再把新函数插到 main 之前（main 在 out 里的位置随搬移前移）
i_main2 = next(i for i, s in enumerate(out) if s.startswith("def main("))
out = out[:i_main2] + new + out[i_main2:]
P.write_text("".join(out), encoding="utf-8")
print("written; lines=%d" % len(out))
