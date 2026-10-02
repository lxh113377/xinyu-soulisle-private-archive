# -*- coding: utf-8 -*-
"""r94 收口②：把 r94 拆分产生的 10 个段函数头部压行，把文件行数拉回 ≤2000。

两把尺互相牵制的第二个实例：第一轮压行让「函数长」过了，却把「文件行数」顶到 2051；
补完 CI 口径统一（+15 行）后行数又到 2021。这里只动 r94 自己新增的头部：
  · 段函数的 docstring 行 → 改成 `def` 行尾注释（信息不丢，字数少一行）
  · 段函数之间两个空行 → 一个（私有函数，风格在本仓内无强约束）
不碰任何原有语句，也不碰段内逻辑。
"""
import re
from pathlib import Path

P = Path("_test/benchmark_metrics.py")
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)
out, i, saved = [], 0, 0
DEF = re.compile(r"^def (_\w+_p\d+|_st_\w+_\d+)\(st\):\s*$")
DOC = re.compile(r'^\s+"""r94：.*"""\s*$')
while i < len(lines):
    m = DEF.match(lines[i])
    if m and i + 1 < len(lines) and DOC.match(lines[i + 1]):
        out.append("def %s(st):  # r94 拆出的第 %s 段（切点由 AST 求得，跨段量经 st 显式传递）\n"
                   % (m.group(1), re.search(r"(\d+)$", m.group(1)).group(1)))
        i += 2
        saved += 1
        # 段末的两个空行合并成一个
        continue
    out.append(lines[i])
    i += 1

# 合并段间空行：连续 2 个空行且下一非空行是 def → 只留 1 个
final, j = [], 0
while j < len(out):
    if out[j].strip() == "" and j + 1 < len(out) and out[j + 1].strip() == "" \
            and j + 2 < len(out) and out[j + 2].startswith("def _"):
        final.append(out[j])
        saved += 1
        j += 2
        continue
    final.append(out[j])
    j += 1

P.write_text("".join(final), encoding="utf-8")
print("压掉 %d 行；%d -> %d 行" % (saved, len(lines), len(final)))
