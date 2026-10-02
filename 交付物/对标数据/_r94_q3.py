# -*- coding: utf-8 -*-
lines = open("_test/offline_shell_check.py", encoding="utf-8").read().splitlines()
print("-- return/raise in try body 227..380 --")
for i in range(226, 380):
    if "return " in lines[i] or "raise " in lines[i]:
        print("%5d| %s" % (i + 1, lines[i].strip()[:70]))
print("-- results / check 使用（前 8 处） --")
n = 0
for i in range(226, len(lines)):
    if "results" in lines[i] or "check(" in lines[i]:
        print("%5d| %s" % (i + 1, lines[i].strip()[:70]))
        n += 1
        if n >= 8:
            break
print("-- 尾段 378..391 原文 --")
for i in range(377, 391):
    print("%5d| %s" % (i + 1, lines[i]))
