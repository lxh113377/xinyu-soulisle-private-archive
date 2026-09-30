# -*- coding: utf-8 -*-
"""r86 录制/截图前的 demo-config 临时切换（proxy 模式）与还原。

用法：
  python _test/_democonfig_switch.py --to-proxy   # 备份并切换为同源代理
  python _test/_democonfig_switch.py --restore    # 按备份逐字节还原并复核 sha256
"""
import hashlib
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "src" / "js" / "demo-config.js"
BAK = ROOT / "_test" / "_democonfig.backup.js"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def to_proxy():
    t = P.read_text(encoding="utf-8")
    if "proxy:" in t:
        print("ALREADY-PROXY")
        return
    BAK.write_bytes(P.read_bytes())
    new, n = re.subn(
        r'base:\s*"https://api\.deepseek\.com/v1",\s*\r?\n\s*key:\s*"sk-[A-Za-z0-9]+",',
        'proxy: "/api/chat",',
        t,
    )
    assert n == 1, f"base/key 两行没找到（n={n}），拒绝盲改"
    P.write_text(new, encoding="utf-8", newline="")
    print("SWITCHED sha_before=%s sha_after=%s" % (sha(BAK)[:16], sha(P)[:16]))


def restore():
    assert BAK.exists(), "没有备份可还原"
    P.write_bytes(BAK.read_bytes())
    BAK.unlink()
    print("RESTORED sha=%s" % sha(P)[:16])


if __name__ == "__main__":
    {"--to-proxy": to_proxy, "--restore": restore}[sys.argv[1]]()
