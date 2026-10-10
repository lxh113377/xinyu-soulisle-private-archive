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
import json
import os
import re
import subprocess
import sys
import time
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


JAR_TOKEN = "soulisle-server.jar"
# 租约放 TEMP 不放仓库：进程身份是本机事实，落进 .ci/ 就成了「本机状态写进提交面」
# （同族教训：台账里混进随工作树变化的数字，CI 上恒假）。
LEASE = Path(os.environ.get("TEMP", ".")) / "xinyu-port-lease.json"


def lease_read():
    """租约名册：{port: {"pid": str, "by": "build_jar", "ts": str}}。读不到=空册，不是「全是我的」。"""
    try:
        d = json.loads(LEASE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def lease_write(port, pid):
    d = lease_read()
    d[str(port)] = {"pid": str(pid), "by": "build_jar",
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        LEASE.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", "utf-8")
    except OSError:
        pass                       # 留痕是旁路：写不动租约不能让构建动作自己崩（同 browser_engine 的纪律）


def classify_holder(cmdline, pid, owned_pids):
    """纯函数：端口持有者归四档（决定「能不能停它」的唯一依据）。

    立此条的一手代价（r104）：`stop_holders()` 原先按端口无脑 `Stop-Process -Force`，
    把并行会话正在用的验证服务端杀掉 3 次（其中一次启动成功 3 秒后被杀）。被杀的一方
    看到的是「服务自己掉了」，红因无法归因 —— 与本项目「整跑不可重入」锁的是同一族事故。
    """
    if str(pid) in {str(x) for x in owned_pids}:
        return "ours"              # 本工具起的，理应由本工具停
    if not cmdline:
        return "unknown"           # 取不到命令行 ⇒ 绝不能当成「无主可杀」（fail-closed）
    if JAR_TOKEN in cmdline.replace("\\", "/").lower():
        return "same-artifact"     # 同一枚 jar，但不是本工具起的（人工/另一会话）
    return "foreign"


def stop_plan(rows, takeover=False):
    """纯函数：rows=[(pid, class, cmdline_summary)] → (可停 pid, 拒绝清单)。

    `takeover` 是人明确授权接管的口子，默认关：**默认只停自己起的**。
    """
    kill, refuse = [], []
    for pid, cls, summary in rows:
        if cls == "ours" or takeover:
            kill.append(pid)
        else:
            refuse.append((pid, cls, summary))
    return kill, refuse


def holder_rows():
    """一次性取回监听者的 (pid, 命令行)，避免每 pid 起一次 PowerShell。"""
    pids = listening_pids()
    if not pids:
        return [], pids
    ps = ("$r=@(); " + " ".join(
        "$r+=Get-CimInstance Win32_Process -Filter ('ProcessId=' + %s);" % ("'%s'" % p)
        for p in pids)
        + "; $r | ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    cmd_of = {}
    for line in (r.stdout or "").splitlines():
        parts = line.split("\t", 1)
        if parts[0].strip().isdigit():
            cmd_of[parts[0].strip()] = (parts[1] if len(parts) > 1 else "").strip()
    owned = [v.get("pid") for v in lease_read().values() if isinstance(v, dict)]
    rows = [(p, classify_holder(cmd_of.get(p, ""), p, owned),
             (cmd_of.get(p) or "<取不到命令行>")[:110]) for p in pids]
    return rows, pids


def stop_holders(takeover=False):
    """停服务前先认属主：只停本工具起的（或 --takeover 明确授权后的）。返回 (killed, refused)。"""
    rows, _ = holder_rows()
    kill, refuse = stop_plan(rows, takeover)
    for pid in kill:
        subprocess.run(["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force"],
                       capture_output=True)
    if kill:
        time.sleep(2)
    return kill, refuse


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
    pr = subprocess.Popen([os.path.join(JDK, "bin", "java.exe"), "-jar", str(JAR), "--server.port=8123"],
                          cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
    lease_write(8123, pr.pid)
    print("  已重新起服务 :8123（密钥仅注入子进程环境，未打印）｜租约登记 pid=%s" % pr.pid)


def selftest():
    """离线自证（不起进程、不碰端口、不读磁盘产物）：属主归类的四形 + 决策表 + 坏租约。

    每条腿都配反例或变异腿 —— 「判据必须可演习」在本仓是硬要求：一条不会红的归类，
    和没有归类等价。
    """
    bad = []
    jar = r"C:\x\server\target\soulisle-server.jar --server.port=8123"
    cases = (
        ((jar, "100", {"100"}), "ours", "租约在册 ⇒ 本工具起的，可停"),
        ((jar, "200", set()), "same-artifact", "同 jar 但非本工具起 ⇒ 拒停（r104 被误杀的就是这一档）"),
        ((r"C:\py\python.exe -m http.server 8123", "300", set()), "foreign", "别家进程"),
        (("", "400", set()), "unknown", "取不到命令行 ⇒ 不许当无主可杀"),
        ((None, "401", set()), "unknown", "命令行 None 同样归 unknown"),
    )
    for args, want, why in cases:
        got = classify_holder(*args)
        if got != want:
            bad.append("classify_holder(%r) 应=%s 实=%s（%s）" % (args[1], want, got, why))
    # 变异腿：把 jar 标识换成不可能的串，same-artifact 必须塌成 foreign（否则那条腿恒真）
    global JAR_TOKEN
    keep = JAR_TOKEN
    try:
        JAR_TOKEN = "__no_such_jar_token__"
        if classify_holder(jar, "200", set()) != "foreign":
            bad.append("变异腿失效：抹掉 jar 标识后仍判 same-artifact ⇒ 归类不认被审对象")
    finally:
        JAR_TOKEN = keep
    rows = [("1", "ours", "a"), ("2", "same-artifact", "b"), ("3", "foreign", "c"), ("4", "unknown", "d")]
    kill, refuse = stop_plan(rows)
    if [p for p, _, _ in rows if p in kill] != ["1"]:
        bad.append("默认档应只停 ours，实停 %s" % kill)
    if len(refuse) != 3:
        bad.append("默认档应拒绝 3 条，实拒 %d ⇒ 非属主被静默放行" % len(refuse))
    kill_all, refuse_all = stop_plan(rows, takeover=True)
    if len(kill_all) != 4 or refuse_all:
        bad.append("--takeover 应全停且零拒绝，实=%s/%s" % (kill_all, refuse_all))
    if stop_plan([])[0]:
        bad.append("空持有者面被读成「可停」⇒ 零输入升格")
    # 坏租约：不存在 / 非 JSON / 非 dict 一律归零，不得当成「全是我的」
    if lease_read() is None:
        bad.append("lease_read 返回 None ⇒ 调用方会炸")
    return finish_selftest(bad)


def finish_selftest(bad):
    print("BUILD-JAR-SELFTEST-%s（属主四形＋变异腿＋决策表两档＋零输入＋坏租约容错，共 %d 条用例）"
          % ("PASS" if not bad else "FAIL", 11))
    for b in bad:
        print("  · " + b)
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--restart", action="store_true", help="构建并验货通过后重新起 8123")
    ap.add_argument("--no-build", action="store_true", help="只验现有产物")
    ap.add_argument("--takeover", action="store_true",
                    help="明确授权停掉非本工具起的持有者（默认拒绝，见 stop_plan）")
    ap.add_argument("--selftest", action="store_true", help="离线自证属主归类，不起进程不碰端口")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not MVN.exists():
        print("BUILD-JAR-ENV-ERROR: 找不到 maven（%s）" % MVN)
        return 2
    if not a.no_build:
        killed, refused = stop_holders(a.takeover)
        print("[1/3] 停掉持有 jar 的进程：%s" % (killed or "无（本工具起的没有）"))
        if refused:
            for pid, cls, summary in refused:
                print("   🔴 拒绝停 pid=%s 归类=%s ｜ %s" % (pid, cls, summary))
            print("   ⇒ 端口被非本工具的进程持有。jar 若被它锁住，`mvn clean` 会失败或截断产物，"
                  "所以本工具不构建。处置：让持有者自己停；或确要接管再跑一次并加 --takeover。")
            print("BUILD-JAR-ENV-UNVERIFIED(端口属主未明)")
            return 2
    if not a.no_build:
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
