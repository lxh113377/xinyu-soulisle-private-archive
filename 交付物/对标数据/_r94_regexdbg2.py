# -*- coding: utf-8 -*-
"""调试 fix_date 为何没匹配：直接在真实文件上试。"""
import re
from pathlib import Path

PAT = re.compile(
    r'subprocess\.run\(\s*\[\s*"date"\s*,\s*"-u"\s*,\s*"\+Y-%m-%dT%H:%M:%SZ"\s*\]\s*,'
    r'\s*capture_output=True\s*,\s*text=True\s*,?\s*\)\.stdout\.strip\(\)',
    re.S)
p = Path("_test/peer_repro_probe.py")
src = p.read_text(encoding="utf-8")
print("文件字符数:", len(src))
print("含 'date' :", src.count('"date"'))
print("findall:", len(PAT.findall(src)))
i = src.find('"date"')
print("上下文:", repr(src[i - 60:i + 140]))
m = PAT.search(src)
print("search:", bool(m))
# 逐字符看关键片段
frag = src[i - 30:i + 130]
print("frag:", repr(frag))
