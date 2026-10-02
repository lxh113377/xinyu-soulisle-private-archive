# -*- coding: utf-8 -*-
"""r94 修同族坑（行版）：8 个 peers probe 用 `date -u` 取时间戳，**Windows 没有这个命令**。

现象（r94 一手）：`peer_repro_probe.py` 跑完 16 仓、打印全部统计，**产物却没落盘** ——
写盘那步 `subprocess.run(["date", "-u", ...])` 抛 FileNotFoundError。不看 stderr 就会
误判「重采成功」（本轮任务 2 就被它悄悄坑了一次）。同族 8 个 probe 全中。

用**按行定位**替换而不是正则：实测正则版在这份源码上失配（`["date", "-u", "+…"]` 那段
死活匹配不上），而行定位不依赖对空白/转义的假设。替换后逐个断言「文件里已无 `date -u`」。
"""
from pathlib import Path

FILES = ["peer_a11y_probe.py", "peer_community_probe.py", "peer_data_rights_probe.py",
         "peer_fault_probe.py", "peer_license_probe.py", "peer_mobile_probe.py",
         "peer_repro_probe.py", "peer_test_asset_probe.py"]
REP = 'datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")'
IMP = "from datetime import datetime, timezone"

for name in FILES:
    p = Path("_test") / name
    lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    out, i, hits = [], 0, 0
    while i < len(lines):
        if '"date", "-u"' in lines[i]:
            j = i
            while j < len(lines) and ".stdout.strip()" not in lines[j]:
                j += 1
            if j >= len(lines):
                out.append(lines[i])
                i += 1
                continue
            # 保留该行在 `=` 之前的赋值前缀（缩进 + 变量名/键名）
            head = lines[i].split("subprocess.run(")[0]
            # ⚠️ 也必须保留 `.stdout.strip()` **之后**的同行尾巴 —— 多行形式里行尾常是 `},`
            # 或 `),`（前一版把整行替换掉，尾巴被吞 ⇒ SyntaxError，6 个文件同时编译失败）。
            tail = lines[j].split(".stdout.strip()", 1)[1] if ".stdout.strip()" in lines[j] else ""
            out.append(head + REP + tail + "\n")
            hits += 1
            i = j + 1
            continue
        out.append(lines[i])
        i += 1
    if not hits:
        print("%-28s 无 `date -u`" % name)
        continue
    src = "".join(out)
    if "from datetime import" not in src:
        src = src.replace("import subprocess\n", "import subprocess\n" + IMP + "\n", 1)
    p.write_text(src, encoding="utf-8")
    left = src.count('"date", "-u"')
    print("%-28s 替换 %d 处；残留 `date -u` = %d" % (name, hits, left))
    assert left == 0, name
print("done")
