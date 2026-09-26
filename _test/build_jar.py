# -*- coding: utf-8 -*-
"""fat jar 构建前置守卫（r38）：把"构建前必须停服务"从一条备忘变成一个动作。

为什么需要它（同一坑两轮踩三次）：Windows 下运行中的 java 进程会锁住
`server/target/soulisle-server.jar`，`mvn clean package` 于是
① `clean` 报 Failed to delete 直接失败，或 ② 更坏：`repackage` 改名失败但旧 jar **已被截断**
（r37 实测只剩 48,907 B），下一步就差点把半成品当 28MB 产物上传。
本脚本按 停 → 构建 → 验货 →（可选）起 的顺序做，且**验货不过就不产资产**：
  · jar 字节数下限（防止截断件）
  · 内嵌 pom.properties 的 version == 当前 `server/pom.xml` 的 version（防止拿旧版当新版）
  · 全包逐条目扫 `sk-` 密钥形态必须 0 命中
  · jar 内不得含前端文件（静态页按 `file:` 直读，入库就成了第三处副本）
用法：python _test/build_jar.py [--restart] [--no-build]
退出码：0=产物可用 1=构建失败或验货不过 2=环境异常（找不到 maven/jdk）
"""
import argparse
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JAR = ROOT / "server" / "target" / "soulisle-server.jar"
JDK = r"C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot"
# Windows 下 python 只能 exec `mvn.cmd`（直接给 sh 版 `mvn` 会 WinError 193 "%1 不是有效的 Win32 应用程序"；
# 同一条命令在 Git Bash 里能跑，是因为 bash 自己解释了那个 shell 脚本 —— 换执行器就要重解析，别照抄）。
_MVN_DIR = Path.home() / ".local/maven/apache-maven-3.9.9/bin"
MVN = next((x for x in (_MVN_DIR / "mvn.cmd", _MVN_DIR / "mvn") if x.exists()), _MVN_DIR / "mvn.cmd")
MIN_JAR_BYTES = 20_000_000
PORTS = ("8123", "8124")


def sh(cmd, **kw):
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def listening_pids():
    ps = ("$r=@(); " + " ".join(
        "$r+=(Get-NetTCPConnection -LocalPort %s -State Listen -ErrorAction SilentlyContinue).OwningProcess;" % p
        for p in PORTS) + "; ($r | Sort-Object -Unique)")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True)
    return [x for x in r.stdout.split() if x.strip().isdigit()]


def stop_holders():
    pids = listening_pids()
    for pid in pids:
        subprocess.run(["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force"],
                       capture_output=True)
    if pids:
        import time
        time.sleep(2)
    return pids


def pom_version():
    t = (ROOT / "server" / "pom.xml").read_text("utf-8", errors="replace")
    m = re.search(r"<artifactId>soulisle-server</artifactId>\s*<version>([^<]+)</version>", t)
    return m.group(1).strip() if m else ""


def verify():
    """返回 (ok, 说明列表)。任何一条不过就不产出资产。"""
    notes, ok = [], True
    if not JAR.exists():
        return False, ["jar 不存在"]
    size = JAR.stat().st_size
    if size < MIN_JAR_BYTES:
        ok = False
        notes.append("体积 %d B < 下限 %d B ⇒ 极可能是被锁期间的截断件" % (size, MIN_JAR_BYTES))
    else:
        notes.append("体积 %d B（过下限）" % size)
    try:
        z = zipfile.ZipFile(JAR)
    except Exception as e:
        return False, ["jar 不是合法 zip：%s" % e]
    props = [n for n in z.namelist() if n.endswith("pom.properties")]
    ver = ""
    if props:
        kv = dict(l.split("=", 1) for l in z.read(props[0]).decode("utf-8", "replace").splitlines() if "=" in l)
        ver = kv.get("version", "")
    want = pom_version()
    if ver != want:
        ok = False
        notes.append("内嵌 version=%r != pom 声明 %r ⇒ 产物不是当前版" % (ver, want))
    else:
        notes.append("内嵌 version=%s == pom" % ver)
    keys, front = [], []
    for n in z.namelist():
        data = z.read(n)
        if re.search(rb"sk-[A-Za-z0-9]{20,}", data):
            keys.append(n)
        if re.search(r"\.(js|html|css)$", n) and "BOOT-INF/classes/static" in n:
            front.append(n)
    notes.append("密钥形态命中 %d 条%s" % (len(keys), ("：" + str(keys[:3]) + " ⇒ 判红") if keys else "（放行）"))
    if keys:
        ok = False
    notes.append("jar 内前端静态件 %d 条%s" % (len(front),
                 "（直读 src/，不该入库 ⇒ 判红）" if front else "（符合'零副本'决策 #2）"))
    if front:
        ok = False
    return ok, notes


def restart_with_key():
    """把回归面恢复起来：密钥从被 ignore 的本地配置读，只注入子进程环境，不打印不落盘。"""
    cfg = ROOT / "src" / "js" / "demo-config.js"
    if not cfg.exists():
        print("  ⚠️ 无本地演示配置，跳过重启（依赖 8123 的套件会记 ENV-UNVERIFIED）")
        return
    m = re.search(r'["\x27](sk-[A-Za-z0-9]{20,})["\x27]', cfg.read_text("utf-8", errors="replace"))
    if not m:
        print("  ⚠️ 本地配置里没解析到密钥，跳过重启")
        return
    env = dict(os.environ)
    env["DEEPSEEK_KEY"] = m.group(1)
    log = open(Path(os.environ["TEMP"]) / "build_jar_server.out", "wb")
    subprocess.Popen([os.path.join(JDK, "bin", "java.exe"), "-jar", str(JAR), "--server.port=8123"],
                     cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
    print("  已重新起服务 :8123（密钥仅注入子进程环境，未打印）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--restart", action="store_true", help="构建并验货通过后重新起 8123")
    ap.add_argument("--no-build", action="store_true", help="只验现有产物")
    a = ap.parse_args()
    if not MVN.exists():
        print("BUILD-JAR-ENV-ERROR: 找不到 maven（%s）" % MVN)
        return 2
    if not a.no_build:
        killed = stop_holders()
        print("[1/3] 停掉持有 jar 的进程：%s" % (killed or "无需（没有监听者）"))
        env = dict(os.environ)
        env["JAVA_HOME"] = JDK
        r = subprocess.run([str(MVN), "-f", "server/pom.xml", "clean", "package", "-q"],
                           cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env)
        out = (r.stdout or "") + (r.stderr or "")
        print("[2/3] mvn rc=%d" % r.returncode)
        for line in out.splitlines():
            if "ERROR" in line:
                print("   ", line[:160])
        if r.returncode != 0:
            print("BUILD-JAR-FAIL: 构建失败（见上面 ERROR 行）")
            return 1
    ok, notes = verify()
    print("[3/3] 验货 %s" % ("PASS" if ok else "FAIL"))
    for n in notes:
        print("    ·", n)
    if ok and a.restart:
        restart_with_key()
    print("BUILD-JAR-%s（产物 %s）" % ("PASS" if ok else "FAIL", JAR))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
