# -*- coding: utf-8 -*-
"""r94：把本轮工具写出的新件工作树字节归一为 LF（与 .gitattributes 的 `* text=auto eol=lf` 对齐）。

背景（r93 已踩过一次）：编辑工具在 Windows 上写出 CRLF，而入库 blob 是 LF ⇒ 工作树字节 != blob 字节
⇒ `eol_parity` 判红（「逐字节/SHA256/字节预算」类主张在他人 clone 上不可复算）。
两个反直觉点：`git status` 显示干净（git 比较时做了归一化）、`git checkout --` 不重写（同一 stat 缓存）。
故按字节直接归一，并逐个打印实际改动量。
"""
import subprocess
from pathlib import Path

out = subprocess.run(["python", "_test/eol_parity_check.py"], capture_output=True,
                     text=True, encoding="utf-8", errors="replace").stdout
paths = sorted({l.split("：", 1)[1].strip() for l in out.splitlines() if "工作树含 CRLF：" in l})
n = 0
for p in paths:
    f = Path(p)
    b = f.read_bytes()
    nb = b.replace(b"\r\n", b"\n")
    if nb != b:
        f.write_bytes(nb)
        n += 1
        print("归一 %-56s CRLF %d 处" % (p, b.count(b"\r\n")))
print("共归一 %d / %d 个文件" % (n, len(paths)))
