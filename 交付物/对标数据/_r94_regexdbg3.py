# -*- coding: utf-8 -*-
"""逐段定位：对**真实文件片段**试每一段正则，找出第一个失配的段。"""
import re
from pathlib import Path

src = Path("_test/peer_repro_probe.py").read_text(encoding="utf-8")
i = src.find('subprocess.run(["date"')
frag = src[i:i + 130]
print("frag =", repr(frag[:130]))
segs = [
    (r'subprocess\.run\(', "run("),
    (r'subprocess\.run\(\[', "run(["),
    (r'\["date"', '[ "date"'),
    (r'\["date", "-u"', '[ "date", "-u"'),
    (r'\["date", "-u", "\+Y', '[ "date", "-u", "+Y'),
    (r'\["date", "-u", "\+%Y-%m-%dT%H:%M:%SZ"\]', '时间串+]'),
    (r'\["date", "-u", "\+%Y-%m-%dT%H:%M:%SZ"\], capture_output=True, text=True\)', '全参数'),
    (r'\)\.stdout\.strip\(\)', '收尾'),
]
for pat, label in segs:
    m = re.search(pat, frag)
    print("%-14s %s" % (label, bool(m)))
    if not m:
        print("   失配于该段；下一段上下文:", repr(frag[:130]))
        break
