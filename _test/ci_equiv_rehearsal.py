"""CI 等效环境复现（一次性工具，跑完必须复原）。

做三件 CI 会做而我本机从不满足的事：
  1) src/js/demo-config.js 换成公网零密钥 stub（CI 是全新 clone，本机版被 gitignore）
  2) jar 在**没有上游密钥**的环境下起（CI 无 secret）
  3) 跑 `--exclude-llm` 电池，把只在"我机器上成立"的判据照出来
含密钥的原文件先按 sha256 备份，脚本结束前必须原样恢复并校验。
"""
import hashlib
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\37533\Desktop\workspace\项目\陪聊")
SRC = ROOT / "src/js/demo-config.js"
BAK = Path(r"C:\Users\37533\AppData\Local\Temp\xinyu_demo_config.local.bak")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def main():
    shutil.copy2(SRC, BAK)
    print("备份 src/js/demo-config.js ->", BAK.name, sha(BAK))
    shutil.copy2(ROOT / "deploy/xinyu/js/demo-config.js", SRC)
    print("已换成公网零密钥 stub:", sha(SRC))

    # 停 jar（无密钥重启）
    ps = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    pid = ""
    for ln in ps.splitlines():
        if ":8123" in ln and "LISTENING" in ln:
            pid = ln.split()[-1]
            break
    if pid:
        subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
        time.sleep(3)
    java = Path(r"C:/Program Files/Eclipse Adoptium/jdk-17.0.20.101-hotspot/bin/java.exe")
    log = open(Path(r"C:/Users/37533/AppData/Local/Temp/xinyu-jar-nok.log"), "wb")
    env_nokey = {k: v for k, v in __import__("os").environ.items() if "DEEPSEEK" not in k and "LLM_KEY" not in k}
    subprocess.Popen([str(java), "-jar", str(ROOT / "server/target/soulisle-server.jar"), "--server.port=8123"],
                     cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, env=env_nokey)
    for _ in range(40):
        try:
            import urllib.request
            with urllib.request.urlopen("http://127.0.0.1:8123/api/health", timeout=3) as r:
                r.read()
                break
        except Exception:
            time.sleep(1)

    r = subprocess.run([sys.executable, "_test/run_all_suites.py", "--exclude-llm"],
                       cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = r.stdout or ""
    keep = [ln for ln in out.splitlines() if " rc=" in ln or ln.strip().startswith("·") or "BATTERY" in ln]
    print("\n".join(keep[-60:]))
    print("CI-EQUIV-EXIT=", r.returncode)

    shutil.copy2(BAK, SRC)
    print("已恢复本机 demo-config:", sha(SRC), "== 备份", sha(SRC) == sha(BAK))


if __name__ == "__main__":
    try:
        main()
    finally:
        if SRC.exists() and sha(SRC) != sha(BAK):
            shutil.copy2(BAK, SRC)
            print("!! 兜底恢复 demo-config 完成")
