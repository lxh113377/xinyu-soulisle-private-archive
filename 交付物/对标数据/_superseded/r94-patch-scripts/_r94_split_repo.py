# -*- coding: utf-8 -*-
"""r94 一次性拆分：`repo_config_check.selftest()`（291 行）按 AST 求得的切点拆成三段。

切点与需传入量由 `_r94_best.py` 实算给出（贪心：段内 ≤140 行 + 跨越变量最少）：
  part_a = 930..1067 (138 行)  产出 ex0, n_all, p
  part_b = 1068..1082 (15 行)  需入参 bad, ex0, n_all, p
  part_c = 1083..1219 (137 行) 需入参 bad，并负责打印与退出码
拆后 `selftest()` 只剩调度 4 行。行为等价性由 `--selftest` 的断言条数（n_mut）验证。
"""
from pathlib import Path

P = Path("_test/repo_config_check.py")
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)


def idx_of(pred, start=0):
    for i in range(start, len(lines)):
        if pred(lines[i]):
            return i
    raise SystemExit("not found")


i_fn = idx_of(lambda s: s.startswith("def selftest():"))
# 用行号定位（1-based）
def block(a, b):          # a,b 为 1-based 闭区间
    return lines[a - 1:b]


def dedent4(s):
    # 这三段本就是 `selftest` 的**函数体**（缩进 4），原样搬即可，**不得**再 dedent：
    # 上一版误把它 dedent 到列 0 ⇒ def 没有体，报 SyntaxError: 'return' outside function。
    # （docker/offline_shell 那两次搬的是 try 体，缩进 8→4，所以那里要 dedent。）
    return s


part_a = block(930, 1067)
part_b = block(1068, 1082)
part_c = block(1083, 1219)
print("part_a %d 行, part_b %d 行, part_c %d 行" % (len(part_a), len(part_b), len(part_c)))
assert part_a[0].strip(), part_a[0]
assert part_c[-1].strip().startswith("return 1 if bad else 0"), part_c[-1]

new = []
new.append("def _st_mut_a(bad):\n")
new.append('    """r94：由 `selftest` 前段整体下移（selftest 原 291 行 > loc_guard 的 150 行门）。\n')
new.append("\n")
new.append("    切点由 AST 求得（段内 ≤140 行且跨越变量最少），不靠目测；本段产出 ex0/n_all/p 供后段用。\n")
new.append('    """\n')
for s in part_a:
    new.append(dedent4(s))
new.append("    return ex0, n_all, p\n")
new.append("\n")
new.append("\n")

new.append("def _st_mut_b(bad, ex0, n_all, p):\n")
new.append('    """r94：由 `selftest` 中段下移（依赖前段产出的 ex0/n_all/p，显式入参不靠闭包）。"""\n')
for s in part_b:
    new.append(dedent4(s))
new.append("\n")
new.append("\n")

new.append("def _st_mut_c(bad):\n")
new.append('    """r94：由 `selftest` 后段下移（含收尾打印与退出码）。"""\n')
for s in part_c:
    new.append(dedent4(s))
new.append("\n")
new.append("\n")

new.append("def selftest():\n")
new.append('    """r94：只留调度——三段断言体已下移到 `_st_mut_a/b/c`。\n')
new.append("\n")
new.append("    拆的动因是 loc_guard 的函数长门（≤150）；拆法保证调用序与原来逐语句一致，\n")
new.append('    故首个失败点、断言条数与退出码都不变（`--selftest` 的 n_mut 是验真点）。\n')
new.append('    """\n')
new.append("    bad = []\n")
new.append("    ex0, n_all, p = _st_mut_a(bad)\n")
new.append("    _st_mut_b(bad, ex0, n_all, p)\n")
new.append("    return _st_mut_c(bad)\n")
new.append("\n")

out = lines[:i_fn] + new + lines[1219:]
P.write_text("".join(out), encoding="utf-8")
print("written; lines=%d" % len(out))
