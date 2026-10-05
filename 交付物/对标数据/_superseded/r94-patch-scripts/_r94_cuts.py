# -*- coding: utf-8 -*-
"""r94 临时：为超长函数自动求**安全切点**。

判据：把函数体切成若干连续段，若某变量在段 A 定义、在段 B（B 在 A 之后）被读，
则该变量跨越切点 ⇒ 该切点不安全（需显式传参）。本脚本只打印「零跨越」的候选切点，
供人工据此决定搬移哪几段（不自动改码）。
"""
import ast
import sys


def analyze(path, func_name):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name == func_name), None)
    if fn is None:
        print("!! func not found", func_name)
        return
    body = fn.body
    print("=" * 72)
    print("%s :: %s()  语句 %d 条，行 %d..%d" % (path, func_name, len(body),
                                                 body[0].lineno, body[-1].end_lineno))
    # 每条顶层语句：定义名集合 / 读取名集合
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
    # 前缀定义集合 / 后缀读取集合
    pre = [set()]
    for i in range(n):
        pre.append(pre[-1] | defs[i])
    suf = [set() for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        suf[i] = suf[i + 1] | uses[i]
    safe = []
    for k in range(1, n):
        cross = (pre[k] & suf[k])          # 在 k 之前定义、在 k 之后被读 ⇒ 跨越
        # 允许跨域：模块级函数/常量（不跨段也能解析）
        cross = {c for c in cross if not (c.isupper() or c.startswith("_mangled"))}
        safe.append((k, body[k].lineno, body[k - 1].end_lineno, sorted(cross)))
    zero = [s for s in safe if not s[3]]
    print("  零跨越切点 %d 个：" % len(zero))
    for k, ln_start, ln_end, _ in zero[:40]:
        print("    在第 %d 条语句前切（= 第 %d 行前；上一段止于 %d 行）" % (k, ln_start, ln_end))
    if not zero:
        few = sorted(safe, key=lambda s: len(s[3]))[:6]
        print("  ⚠️ 无零跨越切点；跨越最少的 6 处（需显式传参）：")
        for k, ln_start, ln_end, cross in few:
            print("    第 %d 行前：跨越 %s" % (ln_start, cross[:8]))


for path, fn in [("_test/benchmark_metrics.py", "selftest"),
                 ("_test/repo_config_check.py", "selftest"),
                 ("_test/a11y_check.py", "main"),
                 ("_test/offline_shell_check.py", "run_runtime"),
                 ("_test/docker_image_sim_check.py", "main"),
                 ("_test/headers_csp_check.py", "run_local"),
                 ("_test/deliverable_inventory_check.py", "fixture_legs"),
                 ("_test/release_governance_check.py", "selftest")]:
    analyze(path, fn)
