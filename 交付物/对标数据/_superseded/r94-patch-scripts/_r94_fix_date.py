# -*- coding: utf-8 -*-
"""r94 修同族坑：8 个 peers probe 用 `date -u` 取时间戳，**Windows 上没有这个命令**。

现象（r94 一手）：`peer_repro_probe.py` 跑完 16 仓、打印全部统计，**但产物没落盘** ——
写盘那一步 `subprocess.run(["date", "-u", ...])` 抛 FileNotFoundError。若不看 stderr，
会以为「重采成功了」，实际台账还是旧的（本轮任务 2 就被它悄悄坑了一次）。
同族面：a11y / community / data_rights / fault / license / mobile / repro / test_asset 共 8 个。

修法：换成标准库 `datetime.now(timezone.utc)`（零依赖、跨平台、语义等价）。
"""
import re
from pathlib import Path

FILES = ["peer_a11y_probe.py", "peer_community_probe.py", "peer_data_rights_probe.py",
         "peer_fault_probe.py", "peer_license_probe.py", "peer_mobile_probe.py",
         "peer_repro_probe.py", "peer_test_asset_probe.py"]

PAT = re.compile(
    r'subprocess\.run\(\s*\[\s*"date"\s*,\s*"-u"\s*,\s*"\+Y-%m-%dT%H:%M:%SZ"\s*\]\s*,'
    r'\s*capture_output=True\s*,\s*text=True\s*,?\s*\)\.stdout\.strip\(\)',
    re.S)
REP = 'datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")'
IMP = "from datetime import datetime, timezone"

for name in FILES:
    p = Path("_test") / name
    src = p.read_text(encoding="utf-8")
    n = len(PAT.findall(src))
    if not n:
        print("%-28s 无 `date -u`，跳过" % name)
        continue
    src = PAT.sub(REP, src)
    if "from datetime import" not in src:
        # 插在 `import subprocess` 之后（保持 import 区字母序的既有风格）
        src = src.replace("import subprocess\n", "import subprocess\n" + IMP + "\n", 1)
    p.write_text(src, encoding="utf-8")
    print("%-28s 替换 %d 处 `date -u` → datetime.now(timezone.utc)" % (name, n))
print("done")
