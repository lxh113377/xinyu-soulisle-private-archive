# -*- coding: utf-8 -*-
"""为 a11y_check.main 的 `with sync_playwright()` 体求「外部依赖 / 对外产出」两组名字。"""
import ast

src = open("_test/a11y_check.py", encoding="utf-8").read()
tree = ast.parse(src)
fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "main")
body = fn.body


def loads(st):
    return {n.id for n in ast.walk(st) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def stores(st):
    s = {n.id for n in ast.walk(st) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    for n in ast.walk(st):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            s.add(n.name)
    return s


i_with = next(k for k, st in enumerate(body) if isinstance(st, ast.With))
pre, mid, post = body[:i_with], [body[i_with]], body[i_with + 1:]
print("with 语句 index=%d  行 %d..%d" % (i_with, body[i_with].lineno, body[i_with].end_lineno))

pre_store = set().union(*[stores(s) for s in pre]) if pre else set()
mid_load = set().union(*[loads(s) for s in mid])
mid_store = set().union(*[stores(s) for s in mid])
post_load = set().union(*[loads(s) for s in post]) if post else set()
post_store = set().union(*[stores(s) for s in post]) if post else set()

print("\n[外部依赖] with 体读到、且在 with 之前定义：", sorted(mid_load & pre_store))
print("\n[对外产出] with 体内定义、且 with 之后被读：", sorted(mid_store & post_load))
print("\n[with 之后新定义] ：", sorted(post_store))
print("\n[with 体内定义但之后未用] ：", sorted(mid_store - post_load - mid_load))
