# -*- coding: utf-8 -*-
"""找 a11y_check.main 内可外提的多行字符串/大字面量（搬数据比搬逻辑安全）。"""
import ast

src = open("_test/a11y_check.py", encoding="utf-8").read()
tree = ast.parse(src)
fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "main")
print("main %d..%d" % (fn.lineno, fn.end_lineno))
out = []


def walk(st, depth=0):
    if isinstance(st, ast.Assign) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
        span = st.end_lineno - st.lineno + 1
        if span >= 4:
            out.append((span, st.lineno, st.end_lineno, getattr(st.targets[0], "id", "?")))
    if isinstance(st, ast.Assign) and isinstance(st.value, ast.Call):
        span = st.end_lineno - st.lineno + 1
        if span >= 6:
            out.append((span, st.lineno, st.end_lineno, getattr(st.targets[0], "id", "?") + " (call)"))
    for ch in ast.iter_child_nodes(st):
        walk(ch, depth + 1)


walk(fn)
for span, a, b, name in sorted(set(out), reverse=True)[:10]:
    print("  %-24s 行 %d..%d = %d 行" % (name, a, b, span))
