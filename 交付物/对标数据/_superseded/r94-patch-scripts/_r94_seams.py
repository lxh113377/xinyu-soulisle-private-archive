# -*- coding: utf-8 -*-
"""r94 临时：为 loc 超限函数找**可安全搬移**的切点。
只打印目标函数体内 indent<=4 的语句行（含行号），供人工挑连续段。
"""
import sys

TARGETS = [
    ("_test/deliverable_inventory_check.py", "def fixture_legs"),
    ("_test/headers_csp_check.py", "def run_local"),
    ("_test/release_governance_check.py", "def selftest"),
    ("_test/offline_shell_check.py", "def run_runtime"),
    ("_test/a11y_check.py", "def main"),
    ("_test/docker_image_sim_check.py", "def main"),
]


def outline(path, marker):
    lines = open(path, encoding="utf-8").read().splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith(marker):
            start = i
            break
    if start is None:
        print("!! not found", path, marker)
        return
    base_ind = len(lines[start]) - len(lines[start].lstrip())
    print("=" * 70)
    print("%s :: %s (line %d, indent %d)" % (path, marker, start + 1, base_ind))
    end = len(lines)
    for j in range(start + 1, len(lines)):
        s = lines[j].strip()
        if s and (len(lines[j]) - len(lines[j].lstrip())) <= base_ind:
            end = j
            break
    print("  block = %d..%d (%d 行)" % (start + 1, end, end - start))
    cnt = 0
    for j in range(start, end):
        ln = lines[j]
        s = ln.strip()
        if not s:
            continue
        ind = len(ln) - len(ln.lstrip())
        if ind <= base_ind + 4:
            print("%5d|%d|%s" % (j + 1, ind, s[:76]))
            cnt += 1
    print("  (顶层语句 %d 条)" % cnt)


for p, m in TARGETS:
    outline(p, m)
