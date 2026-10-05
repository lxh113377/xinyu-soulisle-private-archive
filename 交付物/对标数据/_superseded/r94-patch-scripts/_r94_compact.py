# -*- coding: utf-8 -*-
"""r94 收口：把 r94 拆分新增的「逐行解包 / 逐行收集」压成单行，把文件行数拉回 ≤2000。

拆分本身把 benchmark_metrics.py 从 1918 行顶到 2051 行（函数长门过了，行数门反而红了）——
这就是「两把尺互相牵制」的实例：修一把可能踩另一把。
压行只动 r94 自己新增的那两类行（`x = st['x']` / `st['x'] = x`），不碰任何原有语句。
"""
import re
from pathlib import Path

P = Path("_test/benchmark_metrics.py")
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)

unpack = re.compile(r"^    (\w+) = st\['(\w+)'\]\s*$")
collect = re.compile(r"^    st\['(\w+)'\] = (\w+)\s*$")
out, i, n_un, n_col = [], 0, 0, 0
while i < len(lines):
    m = unpack.match(lines[i])
    if m:
        names, j = [], i
        while j < len(lines):
            mm = unpack.match(lines[j])
            if not mm or mm.group(1) != mm.group(2):
                break
            names.append(mm.group(1))
            j += 1
        if len(names) > 1:
            # 注意：右值必须是 `st['a'], st['b']` 两个键，**不是** `st['a', 'b']`（那是元组键 ⇒ KeyError）
            out.append("    %s = %s\n" % (", ".join(names), ", ".join("st[%r]" % n for n in names)))
            n_un += len(names) - 1
            i = j
            continue
    m2 = collect.match(lines[i])
    if m2:
        names, j = [], i
        while j < len(lines):
            mm = collect.match(lines[j])
            if not mm or mm.group(1) != mm.group(2):
                break
            names.append(mm.group(1))
            j += 1
        if len(names) > 1:
            out.append("    st.update(%s)\n" % ", ".join("%s=%s" % (n, n) for n in names))
            n_col += len(names) - 1
            i = j
            continue
    out.append(lines[i])
    i += 1

P.write_text("".join(out), encoding="utf-8")
print("解包行压缩省 %d 行，收集行压缩省 %d 行；%d -> %d 行"
      % (n_un, n_col, len(lines), len(out)))
