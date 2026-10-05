# -*- coding: utf-8 -*-
"""r94 验真（修正版）：实跑 HEAD 版与当前版的 `--selftest`，逐字比对 PASS 行 + 退出码。

上一版用正则去源码里抓 PASS 行，抓到的是 print 语句里的 f-string 源码（13379 字符），
不是运行输出 ⇒ 比对无意义。教训：**验真必须比运行结果，不能比源码文本**。
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(".").resolve()
tmp = ROOT / "交付物" / "对标数据" / "_r94_head_bench.py"
tmp.write_text(subprocess.run(["git", "show", "HEAD:_test/benchmark_metrics.py"],
                              capture_output=True, text=True, encoding="utf-8",
                              cwd=ROOT).stdout, encoding="utf-8")

base = subprocess.run([sys.executable, str(tmp), "--selftest"], capture_output=True,
                      text=True, encoding="utf-8", errors="replace", cwd=ROOT)
now = subprocess.run([sys.executable, "_test/benchmark_metrics.py", "--selftest"],
                     capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
b = [l for l in base.stdout.splitlines() if "SELFTEST-" in l]
n = [l for l in now.stdout.splitlines() if "SELFTEST-" in l]
print("HEAD 版 rc=%d ｜ 行数=%d ｜ 长度=%d" % (base.returncode, len(b), len(b[0]) if b else -1))
print("当前  版 rc=%d ｜ 行数=%d ｜ 长度=%d" % (now.returncode, len(n), len(n[0]) if n else -1))
print("逐字相同:", b == n and base.returncode == now.returncode)
if b != n:
    print("HEAD:", (b[0][:160] if b else "<无>"))
    print("当前:", (n[0][:160] if n else "<无>"))
    if base.stderr.strip():
        print("HEAD stderr:", base.stderr.strip()[:200])
    if now.stderr.strip():
        print("当前 stderr:", now.stderr.strip()[:200])
tmp.unlink()
