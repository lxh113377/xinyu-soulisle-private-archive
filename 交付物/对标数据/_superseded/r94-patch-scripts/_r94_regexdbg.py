# -*- coding: utf-8 -*-
"""调试：为什么上一版正则没匹配上（逐段试）。"""
import re

S = '        ts = subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True).stdout.strip()'
parts = [
    (r'subprocess\.run\(', "run("),
    (r'subprocess\.run\(\s*\[', "run(["),
    (r'\["date",\s*"-u",', '["date", "-u",'),
    (r'"\+%Y-%m-%dT%H:%M:%SZ"\]', "ts 串 + ]"),
    (r'\]\s*,\s*capture_output=True\s*,\s*text=True\)', "参数尾巴"),
    (r'\)\.stdout\.strip\(\)', "收尾"),
]
for pat, label in parts:
    print("%-12s %s" % (label, bool(re.search(pat, S))))
FULL = (r'subprocess\.run\(\s*\[\s*"date"\s*,\s*"-u"\s*,\s*"\+%Y-%m-%dT%H:%M:%SZ"\s*\]\s*,'
        r'\s*capture_output=True\s*,\s*text=True\s*,?\s*\)\.stdout\.strip\(\)')
print("FULL(无 DOTALL) =", bool(re.search(FULL, S)))
print("FULL(有 DOTALL) =", bool(re.search(FULL, S, re.S)))
