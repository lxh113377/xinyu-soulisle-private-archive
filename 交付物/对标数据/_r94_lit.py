# -*- coding: utf-8 -*-
"""r94 临时：在超限函数里找**可整块提到模块级**的大字面量（多行字符串/列表/字典）。
理由：搬数据比搬逻辑安全得多——没有变量捕获、没有控制流，改完 selftest 逐条腿数不变即可证。
"""
import ast

TARGETS = [("_test/headers_csp_check.py", "run_local"),
           ("_test/docker_image_sim_check.py", "main"),
           ("_test/offline_shell_check.py", "run_runtime"),
           ("_test/a11y_check.py", "main"),
           ("_test/repo_config_check.py", "selftest"),
           ("_test/benchmark_metrics.py", "selftest")]


def big_literals(path, fn_name):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == fn_name), None)
    if fn is None:
        return
    print("=" * 72)
    print("%s :: %s()  行 %d..%d（%d 行）" % (path, fn_name, fn.lineno, fn.end_lineno,
                                              fn.end_lineno - fn.lineno))
    cands = []
    for st in fn.body:
        if isinstance(st, ast.Assign) and isinstance(st.value, (ast.Constant, ast.List,
                                                                ast.Dict, ast.JoinedStr)):
            span = st.end_lineno - st.lineno + 1
            if span >= 5:
                tgt = st.targets[0]
                name = getattr(tgt, "id", "?")
                cands.append((span, st.lineno, st.end_lineno, name))
        if isinstance(st, ast.Assign) and isinstance(st.value, ast.Call):
            span = st.end_lineno - st.lineno + 1
            if span >= 12:
                tgt = st.targets[0]
                name = getattr(tgt, "id", "?")
                cands.append((span, st.lineno, st.end_lineno, name + " (call/多行)"))
    for span, a, b, name in sorted(cands, reverse=True)[:6]:
        print("   %-28s 行 %d..%d  = %d 行" % (name, a, b, span))


for p, f in TARGETS:
    big_literals(p, f)
