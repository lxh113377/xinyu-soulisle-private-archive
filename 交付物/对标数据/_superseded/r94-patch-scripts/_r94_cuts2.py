# -*- coding: utf-8 -*-
"""r94 临时（第二版）：把「累加器」（将作为显式参数传入的 bad/fail/ok 等）排除后再求切点。
原因：第一版把 `bad` 也算成跨越，于是处处不可切；而 `bad` 这类累加器本来就是要显式传参的。
"""
import ast

IGNORE = {"bad", "fail", "ok", "total", "n_ok", "errs", "warns", "probe", "cases"}


def analyze(path, func_name, extra_ignore=()):
    ig = IGNORE | set(extra_ignore)
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name == func_name), None)
    if fn is None:
        print("!! not found", func_name)
        return
    body = fn.body
    print("=" * 72)
    print("%s :: %s()  顶层语句 %d 条，行 %d..%d" % (path, func_name, len(body),
                                                    body[0].lineno, body[-1].end_lineno))
    defs, uses = [], []
    for st in body:
        d = set()
        for n in ast.walk(st):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                d.add(n.id)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                d.add(n.name)
        u = set()
        for n in ast.walk(st):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                u.add(n.id)
        defs.append(d)
        uses.append(u)
    n = len(body)
    pre = [set()]
    for i in range(n):
        pre.append(pre[-1] | defs[i])
    suf = [set() for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        suf[i] = suf[i + 1] | uses[i]
    rows = []
    for k in range(1, n):
        cross = {c for c in (pre[k] & suf[k]) if c not in ig}
        rows.append((k, body[k].lineno, sorted(cross)))
    zero = [r for r in rows if not r[2]]
    print("  零跨越切点 %d 个（行号）：%s" % (len(zero), [r[1] for r in zero][:30]))
    few = sorted(rows, key=lambda r: len(r[2]))[:5]
    print("  跨越最少的 5 处：")
    for k, ln, cross in few:
        print("    第 %d 行前：%s" % (ln, cross[:10]))


for path, fn in [("_test/repo_config_check.py", "selftest"),
                 ("_test/benchmark_metrics.py", "selftest"),
                 ("_test/a11y_check.py", "main"),
                 ("_test/offline_shell_check.py", "run_runtime"),
                 ("_test/docker_image_sim_check.py", "main"),
                 ("_test/headers_csp_check.py", "run_local")]:
    analyze(path, fn)
