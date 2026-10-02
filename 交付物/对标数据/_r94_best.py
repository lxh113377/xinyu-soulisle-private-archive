# -*- coding: utf-8 -*-
"""r94：为超长 selftest/main 求「最优切点」——贪心取段内 ≤LIMIT 行且跨越变量最少的切点。
输出即可作为下一轮拆分的施工图（含每段要显式传入的变量名）。
"""
import ast

LIMIT = 140


def analyze(path, fn_name):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == fn_name)
    body = fn.body

    def loads(st):
        return {n.id for n in ast.walk(st) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}

    def stores(st):
        s = {n.id for n in ast.walk(st) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        for n in ast.walk(st):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                s.add(n.name)
        return s

    n = len(body)
    pre = [set()]
    for i in range(n):
        pre.append(pre[-1] | stores(body[i]))
    suf = [set() for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        suf[i] = suf[i + 1] | loads(body[i])

    print("=" * 74)
    print("%s :: %s()  行 %d..%d" % (path, fn_name, body[0].lineno, body[-1].end_lineno))
    start = body[0].lineno
    cur = start
    idx = 0
    seg = 0
    while idx < n:
        best = None
        for k in range(idx + 1, n + 1):
            end = body[k - 1].end_lineno
            if end - cur + 1 > LIMIT and k > idx + 1:
                break
            if k == n:
                best = (k, end, set())
                break
            cross = pre[k] & suf[k]
            if best is None or len(cross) < len(best[2]):
                best = (k, body[k].lineno, cross)
        if best is None:
            print("   ⚠️ 段 %d 找不到 ≤%d 行的切点（第 %d 行起）" % (seg + 1, LIMIT, cur))
            break
        k, nextline, cross = best
        seg += 1
        print("   段%d: %d..%d (%d 行)  下一段起 %d  需传入: %s"
              % (seg, cur, body[k - 1].end_lineno, body[k - 1].end_lineno - cur + 1,
                 nextline, sorted(cross)[:12]))
        cur = nextline
        idx = k
        if k >= n:
            break


for p, f in [("_test/repo_config_check.py", "selftest"),
             ("_test/benchmark_metrics.py", "selftest"),
             ("_test/a11y_check.py", "main")]:
    analyze(p, f)
