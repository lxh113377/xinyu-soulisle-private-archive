# -*- coding: utf-8 -*-
lines = open("_test/a11y_check.py", encoding="utf-8").read().splitlines()
start = None
for i, l in enumerate(lines):
    if l.startswith("def main("):
        start = i
        break
print("main@%d" % (start + 1))
for i in range(start, len(lines)):
    ln = lines[i]
    s = ln.strip()
    if not s:
        continue
    ind = len(ln) - len(ln.lstrip())
    if ind <= 4:
        print("%5d|%d|%s" % (i + 1, ind, s[:76]))
    if i > start and ind == 0 and s and not s.startswith("#"):
        break
