# -*- coding: utf-8 -*-
"""r94 通用拆分器：把一个「扁平语句列表」的长函数按给定切点拆成若干 ≤150 行的函数。

跨段变量用显式 `st` 字典传递（段首解包 / 段尾收集），不靠闭包或 globals。
剔除推导式局部变量（py3 不外泄，留着会生成不存在的 `st['p']` ⇒ NameError，repo_config 已踩）。
段内原有 `return 1` 早退路径不动；每段尾追加「收集行 + return 0」表示本段通过。

用法：python _r94_split_generic.py <file> <func> <cut1,cut2,...>
"""
import ast
import sys
from pathlib import Path


def comp_scoped(st):
    out = set()
    for n in ast.walk(st):
        if isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for t in ast.walk(n):
                if isinstance(t, ast.Name) and isinstance(t.ctx, ast.Store):
                    out.add(t.id)
    return out


def stores(sts):
    s = set()
    for st in sts:
        s |= {n.id for n in ast.walk(st) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        s |= {n.name for n in ast.walk(st)
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        s -= comp_scoped(st)
    return s


def loads(sts):
    u = set()
    for st in sts:
        u |= {n.id for n in ast.walk(st) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    return u


def main():
    path, func, cuts = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3].split(",")]
    P = Path(path)
    src = P.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func)
    body = fn.body
    stmt_line = [st.lineno for st in body]
    idxs = [next(i for i, ln in enumerate(stmt_line) if ln >= c) for c in cuts]
    segs, prev = [], 0
    for k in idxs + [len(body)]:
        segs.append((prev, k))
        prev = k
    seg_store = [stores(body[a:b]) for a, b in segs]
    seg_load = [loads(body[a:b]) for a, b in segs]
    print("%s :: %s()  %d..%d（%d 段）" % (path, func, body[0].lineno, body[-1].end_lineno, len(segs)))

    out_funcs, disp = [], []
    for i, (a, b) in enumerate(segs):
        params = sorted((set().union(*seg_store[:i]) if i else set()) & seg_load[i])
        rets = sorted(seg_store[i] & (set().union(*seg_load[i + 1:]) if i + 1 < len(segs) else set()))
        # r94 修正（实测崩溃点 `_main_p1` UnboundLocalError: audit）：**条件定义**的名字
        # （只在 `if args.xxx:` 分支里赋值）不能无条件收集。判据 = 该名字的首次赋值出现在
        # If/For/While/With/Try 内部。此类名字用 `locals().get()` 容错收集，其余照旧直接引用 ——
        # 不用「段首即重定义就剔除入参」那套：它会把 `if` 子句里的赋值误判成段首赋值（实测踩到）。
        cond = set()
        for st in body[a:b]:
            if isinstance(st, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                continue
            for nm in stores([st]):
                cond |= {nm}
        a_line, b_line = body[a].lineno, body[b - 1].end_lineno
        seg_lines = lines[a_line - 1:b_line]
        print("  段%d %d..%d（%d 行）入参%d ｜ 交出%d"
              % (i + 1, a_line, b_line, len(seg_lines), len(params), len(rets)))
        assert len(seg_lines) <= 150, (i, len(seg_lines))
        head = ["def _%s_p%d(st):\n" % (func, i + 1),
                '    """r94：`%s` 第 %d 段（切点由 AST 求得；跨段量经 `st` 显式传递）。"""\n' % (func, i + 1)]
        head += ["    %s = st[%r]\n" % (nm, nm) for nm in params]
        cond_rets = [nm for nm in rets if nm in cond]
        tail = ["    st[%r] = %s\n" % (nm, ("locals().get(%r)" % nm) if nm in cond else nm)
                for nm in rets] + ["    return 0\n"]
        if cond_rets:
            print("  段%d 条件定义（容错收集）：%s" % (i + 1, cond_rets))
        out_funcs.extend(head + seg_lines + tail + ["\n", "\n"])
        disp.append("    if _%s_p%d(st):\n        return 1\n" % (func, i + 1))

    new = out_funcs + ["def %s():\n" % func,
                      '    """r94：只留调度——各段已下移到 `_%s_p1..%d`（跨段量走显式 `st`）。"""\n'
                      % (func, len(segs)), "    st = {}\n"] + disp + ["    return 0\n", "\n"]
    out = lines[:fn.lineno - 1] + new + lines[fn.end_lineno:]
    P.write_text("".join(out), encoding="utf-8")
    print("written; lines=%d" % len(out))


main()
