# -*- coding: utf-8 -*-
"""r94：`benchmark_metrics.selftest()`（625 行）按 AST 求得的切点拆成 6 段。

跨段变量用**显式 state 字典** `st` 传递（段首解包 / 段尾收集），不靠闭包也不靠 globals：
- 段内若 `return 1`（首腿失败即停的既有语义），收集行不执行 —— 但此时后续段也不会跑，
  所以 `st` 不更新是安全的（这条等价性已逐段核对）。
- 推导式局部变量（`[x.name for x in ...]`）在 py3 不外泄，**必须**从跨越集里剔除：
  不剔会生成 `st['p']` 这种不存在的键（repo_config 那次已实测踩到 ⇒ NameError）。

验真点：拆分前后 `--selftest` 必须打印**逐字相同**的那行 SELFTEST-PASS 且 rc=0。
"""
import ast
from pathlib import Path

P = Path("_test/benchmark_metrics.py")
src = P.read_text(encoding="utf-8")
lines = src.splitlines(keepends=True)
tree = ast.parse(src)
fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "selftest")
body = fn.body
print("selftest %d..%d（%d 条顶层语句）" % (body[0].lineno, body[-1].end_lineno, len(body)))

# 切点（1-based 行，切在该行所属语句之前）
CUTS = [1178, 1296, 1405, 1506, 1629]
stmt_line = [st.lineno for st in body]
idxs = []
for c in CUTS:
    k = next(i for i, ln in enumerate(stmt_line) if ln >= c)
    idxs.append(k)
segs = []
prev = 0
for k in idxs + [len(body)]:
    segs.append((prev, k))
    prev = k
print("分段行数：", [body[b - 1].end_lineno - body[a].lineno + 1 for a, b in segs])


def comp_scoped(st):
    """只在该推导式内部被赋值的名字（py3 不外泄）⇒ 不进跨越集。"""
    out = set()
    for n in ast.walk(st):
        if isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for t in ast.walk(n):
                if isinstance(t, ast.Name) and isinstance(t.ctx, ast.Store):
                    out.add(t.id)
    return out


def stores(sts, skip_comp=True):
    s = set()
    for st in sts:
        s |= {n.id for n in ast.walk(st) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        s |= {n.name for n in ast.walk(st)
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        if skip_comp:
            s -= comp_scoped(st)
    return s


def loads(sts):
    u = set()
    for st in sts:
        u |= {n.id for n in ast.walk(st) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    return u


seg_store = [stores(body[a:b]) for a, b in segs]
seg_load = [loads(body[a:b]) for a, b in segs]

new_funcs = []
prev_store = set()
for i, (a, b) in enumerate(segs):
    params = sorted((set().union(*seg_store[:i]) if i else set()) & seg_load[i])
    rets = sorted(seg_store[i] & (set().union(*seg_load[i + 1:]) if i + 1 < len(segs) else set()))
    a_line, b_line = body[a].lineno, body[b - 1].end_lineno
    seg_lines = lines[a_line - 1:b_line]
    print("段%d %d..%d（%d 行）入参%d %s ｜ 交出%d %s"
          % (i + 1, a_line, b_line, len(seg_lines), len(params), params, len(rets), rets))
    head = ["def _st_selftest_%d(st):\n" % (i + 1),
            '    """r94：`selftest` 第 %d 段（切点由 AST 求得，跨段量经 `st` 显式传递）。"""\n' % (i + 1)]
    for nm in params:
        head.append("    %s = st[%r]\n" % (nm, nm))
    tail = []
    for nm in rets:
        tail.append("    st[%r] = %s\n" % (nm, nm))
    # 段尾形态多样（`return 0` / `return 1` / 普通赋值），故**无条件**在段尾追加
    # 「收集行 + return 0」= 本段通过、交给下一段；段内原有的 `return 1` 早退路径不动。
    # （若段内原本以 `return 0` 收尾，追加的收集行不可达 —— 但那时已是最后一段，无副作用。）
    seg_lines = seg_lines + tail + ["    return 0\n"]
    new_funcs.extend(head + seg_lines + ["\n", "\n"])
    prev_store |= seg_store[i]

disp = ["def selftest():\n",
        '    """r94：只留调度——六段断言体已下移到 `_st_selftest_1..6`。\n',
        "\n",
        "    跨段变量走显式 `st` 字典（段首解包 / 段尾收集），不靠闭包或 globals；\n",
        "    任一段 `return 1` 即整轮失败（与拆分前「首腿失败即停」同语义）。\n",
        '    """\n',
        "    st = {}\n"]
for i in range(len(segs)):
    disp.append("    if _st_selftest_%d(st):\n        return 1\n" % (i + 1))
disp += ["    return 0\n", "\n"]

out = lines[:fn.lineno - 1] + new_funcs + disp + lines[fn.end_lineno:]
P.write_text("".join(out), encoding="utf-8")
print("written; lines=%d" % len(out))
