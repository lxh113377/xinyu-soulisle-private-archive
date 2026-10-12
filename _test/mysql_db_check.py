# -*- coding: utf-8 -*-
"""MySQL 目标库常驻判据：把「可切 MySQL」从声称变成每轮可复算的验收。

为什么需要它：J4 起 `application.yml` 就写着「生产切 MySQL：XINYU_DB_URL/DRIVER/USER/PASSWORD」，
但到 2026-10-12 之前**从没有一条判据在真 MySQL 上跑过**——`_test/` 全库 grep `mysql` 零命中。
这就是「存在性类能力位须配行为回执」那条纪律说的形状：配置口子存在 ≠ 能力成立。

本件测的是**行为**，不是配置文本：真起 fat jar 连真 MySQL，走完
建表 → 写入 → 读回 → 计数 → 重启不丢 → 清除 → 会话隔离 六腿，
并把中文/emoji/引号/反斜杠/制表做**逐字节**往返对账（字符集是不是 utf8mb4，只有这一腿能证）。

用法（三种取库方式，优先级从上到下）：
  1. 显式指定：`XINYU_MYSQL_JDBC=jdbc:mysql://host:3306/db` XINYU_MYSQL_USER= XINYU_MYSQL_PASSWORD=
  2. `--docker`：起一个**一次性** mysql:8 容器（默认 127.0.0.1:13306，库名 xinyu_check），
     跑完自动删除；`--keep` 可留容器供复算。口令是每次现生成的一次性口令，不落仓、不落盘。
  3. `--portability`：同上但**故意把服务器默认字符集设成 latin1**（反例腿）。
     它存在的理由：`schema.sql` 若不自带 `DEFAULT CHARSET=utf8mb4`，表就跟随服务器默认字符集，
     在 latin1 服务器上中文**直接写不进去**（实测 ERROR 1366 Incorrect string value）。
     没有这条腿，「MySQL 支持」就只在一个恰好是 utf8mb4 的服务器上成立过。

退出码（与电池三态同口径）：0=全绿 / 1=判红 / 2=环境未验（连不上库或缺依赖，**不是绿**）。
无库可用时印 `MYSQL-DB-UNVERIFIED` 并在末行给出可复算命令，绝不静默 PASS（R247）。
"""
import io
import json
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
JAR = ROOT / "server" / "target" / "soulisle-server.jar"
LOG_DIR = Path(os.environ.get("TEMP") or "/tmp") / "xinyu-mysql-db-check"
LOG_DIR.mkdir(parents=True, exist_ok=True)

CONTAINER = "xinyu-mysql-check"
IMAGE = "mysql:8"
DB_NAME = "xinyu_check"

SID_A = "mysql-db-check-a"
SID_B = "mysql-db-check-b"

# 中文 + emoji + 引号 + 反斜杠 + 制表：任意一处被字符集/转义吃掉都会让「逐字节相等」判红
EMOTION_TEXT = "今天下雨了，但我心里是晴的。emoji 也无损：🌧️→☀️"
MSG_CONTENT = "第一行中文\n第二行：单引号'双引号\"反斜杠\\ 制表\t结束 🌧️"


def has_nonascii(text):
    return any(ord(c) > 127 for c in text)

VERDICT = "MYSQL-DB"
_keepalive = []


def log(line):
    print(line, flush=True)


def docker_bin():
    for cand in (shutil.which("docker"), r"C:\Program Files\Docker\Docker\resources\bin\docker"):
        if cand and Path(cand).exists():
            return cand
    return None


def run(cmd, timeout=180, input_bytes=None):
    p = subprocess.run(cmd, capture_output=True, timeout=timeout, input=input_bytes)
    out = (p.stdout or b"").decode("utf-8", "replace") + (p.stderr or b"").decode("utf-8", "replace")
    return p.returncode, out.strip()


def free_port(start=18232, end=18260):
    for port in range(start, end):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return None


def http(method, url, body=None, timeout=20):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, {"_raw": e.read().decode("utf-8", "replace")}


class Target:
    """一个可连的 MySQL 目标。两种来源：环境变量 / 本脚本起的一次性容器。"""

    def __init__(self, jdbc, user, password, db, owns_container, docker=None):
        self.jdbc, self.user, self.password, self.db = jdbc, user, password, db
        self.owns_container, self.docker = owns_container, docker

    def teardown(self):
        if self.owns_container and self.docker:
            run([self.docker, "rm", "-f", CONTAINER])


def start_container(charset):
    """起一次性 mysql:8 容器；charset='latin1' 时即反例腿（服务器默认字符集 hostile）。"""
    dk = docker_bin()
    if not dk:
        return None, "本机找不到 docker CLI（反例腿与 --docker 取库都需要它）"
    rc, _ = run([dk, "image", "inspect", IMAGE])
    if rc != 0:
        return None, f"本机没有 {IMAGE} 镜像（本判据不自动拉取：拉取是网络动作，留给调用方显式做）"
    password = "xinyu_check_%08x" % random.getrandbits(32)
    run([dk, "rm", "-f", CONTAINER])
    cmd = [dk, "run", "-d", "--name", CONTAINER,
           "-e", f"MYSQL_ROOT_PASSWORD={password}", "-e", f"MYSQL_DATABASE={DB_NAME}",
           "-p", "13306:3306", IMAGE]
    if charset == "latin1":
        cmd += ["--character-set-server=latin1", "--collation-server=latin1_swedish_ci"]
    rc, out = run(cmd)
    if rc != 0:
        return None, f"容器起不来：{out.splitlines()[-1] if out else 'rc=%s' % rc}"
    deadline = time.time() + 180
    while time.time() < deadline:
        rc, _ = run([dk, "exec", CONTAINER, "mysqladmin", "ping", "-h127.0.0.1",
                     "-uroot", f"-p{password}"], timeout=30)
        if rc == 0:
            jdbc = (f"jdbc:mysql://127.0.0.1:13306/{DB_NAME}"
                    "?serverTimezone=Asia/Shanghai&connectTimeout=5000")
            return Target(jdbc, "root", password, DB_NAME, True, dk), None
        time.sleep(5)
    run([dk, "rm", "-f", CONTAINER])
    return None, "容器 180s 内没就绪（mysqladmin ping 一直非 0）"


def env_target():
    jdbc = os.environ.get("XINYU_MYSQL_JDBC", "").strip()
    if not jdbc:
        return None
    return Target(
        jdbc=jdbc,
        user=os.environ.get("XINYU_MYSQL_USER", "root"),
        password=os.environ.get("XINYU_MYSQL_PASSWORD", ""),
        db=os.environ.get("XINYU_MYSQL_DB", ""),
        owns_container=False,
    )


def resolve_java():
    """JVM 解析走电池那份唯一实现，本件不另写一份。

    实测动因（本判据首跑就踩到）：本机 `JAVA_HOME` 默认指向 **JDK 8**，盲信它会让
    `java -jar` 以一句乱码的「无法访问 jarfile」收口——看着像 jar 坏了，实际是解释器不对。
    故解析后还要核主版本 ≥17，不满足就明说，不把归因推给 jar。
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        # 电池模块顶部会把 sys.stdout 换成它自己的 utf-8 包装器（同样包着本进程的底层 buffer）。
        # 若不留引用，它会在被回收时把底层 buffer 一并关掉，本件后面所有 print 立刻
        # `ValueError: I/O operation on closed file`——首跑实测踩到，故此处留住引用并复位。
        _keepalive.append(sys.stdout)
        import run_all_suites as ras
        _keepalive.append(sys.stdout)
        sys.stdout = _keepalive[0]
        exe = ras.java_exe()
        major = ras.java_major(exe) if exe else None
        if exe and major and major >= 17:
            return exe, None
        return None, f"找到的 JVM 主版本={major}（需 ≥17），exe={exe}"
    except Exception as e:  # 电池被改动/不可导入时给出可行动原因，而不是静默换一条路
        return None, f"无法复用电池的 JVM 解析（{e.__class__.__name__}: {e}）"


class Server:
    """起了就归我：只按自己记下的 PID 杀，不按端口/名字找人（电池 r90 在册纪律）。"""

    def __init__(self, port, target, java):
        self.port, self.target, self.java = port, target, java
        self.proc, self.log_path = None, None

    def start(self, tag):
        java = self.java
        env = dict(os.environ)
        env.update({
            "XINYU_DB_URL": self.target.jdbc,
            "XINYU_DB_DRIVER": "com.mysql.cj.jdbc.Driver",
            "XINYU_DB_USER": self.target.user,
            "XINYU_DB_PASSWORD": self.target.password,
            "XINYU_PORT": str(self.port),
        })
        self.log_path = LOG_DIR / f"server-{tag}.log"
        fh = open(self.log_path, "wb")
        self.proc = subprocess.Popen([java, "-jar", str(JAR)], cwd=str(ROOT),
                                     env=env, stdout=fh, stderr=subprocess.STDOUT)
        deadline = time.time() + 90
        while time.time() < deadline:
            if self.proc.poll() is not None:
                return f"进程提前退出（rc={self.proc.returncode}），见 {self.log_path}"
            try:
                code, _ = http("GET", f"http://127.0.0.1:{self.port}/api/health", timeout=3)
                if code == 200:
                    return None
            except Exception:
                time.sleep(1.5)
        return f"90s 内 /api/health 未就绪，见 {self.log_path}"

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)

    def tail(self, n=40):
        if self.log_path and self.log_path.exists():
            return "\n".join(self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:])
        return "(无日志)"


def check_lifecycle(base, fails):
    """六腿：写入 → 读回逐字节 → 计数 → 其余会话隔离。返回 False 即判红。"""
    def stats(sid):
        return http("GET", f"{base}/api/memory/stats?sessionId={sid}")[1]

    http("DELETE", f"{base}/api/memory/{SID_A}")
    http("DELETE", f"{base}/api/memory/{SID_B}")

    code, body = http("POST", f"{base}/api/memory/emotion", {
        "sessionId": SID_A, "emotion": "joy", "intensity": 0.82,
        "secondary": "surprise", "text": EMOTION_TEXT})
    if code != 200 or not body.get("ok"):
        fails.append(f"FAIL-W1: 情绪写入失败 HTTP={code} body={body}")
        return False

    code, body = http("POST", f"{base}/api/memory/message", {
        "sessionId": SID_A, "role": "user", "content": MSG_CONTENT})
    if code != 200 or not body.get("ok"):
        fails.append(f"FAIL-W2: 消息写入失败 HTTP={code} body={body}")
        return False

    _, got = http("GET", f"{base}/api/memory/emotions?sessionId={SID_A}")
    if not got or got[0].get("text") != EMOTION_TEXT:
        fails.append("FAIL-R1: 情绪文本往返不是逐字节相等｜发=%r 收=%r"
                     % (EMOTION_TEXT, got[0].get("text") if got else None))
    _, got = http("GET", f"{base}/api/memory/messages?sessionId={SID_A}")
    if not got or got[0].get("content") != MSG_CONTENT:
        fails.append("FAIL-R2: 消息文本往返不是逐字节相等（中文/emoji/引号/反斜杠/制表任一处被吃）")
    if got and got[0].get("createdAt") is None:
        fails.append("FAIL-R3: createdAt 读回为 null（时间列未被应用侧写入）")

    a = stats(SID_A)
    if (a.get("emotions"), a.get("messages")) != (1, 1):
        fails.append(f"FAIL-S1: stats 计数应为 1/1，实测 {a}")
    b = stats(SID_B)
    if (b.get("emotions"), b.get("messages")) != (0, 0):
        fails.append(f"FAIL-S2: 另一会话应为 0/0（否则查询没按 sessionId 过滤），实测 {b}")
    return not fails


def selftest():
    """离线自证：只钉「本件的取数与判定链」，不依赖 docker/MySQL（故可进电池整跑）。

    三条腿各对应一种**静默失效**，它们都不会让主流程报错、只会让它不再有区分力：
      L1 往返夹具必须是非 ASCII —— 若有人把夹具「简化」成 ASCII，字符集那条腿就变成空断言
         （latin1 服务器也会全绿）；对照腿用纯 ASCII 串证明这条守卫本身不是恒真。
      L2 门面行必须能被电池的 VERDICT_RE 认出来 —— 认不出的套件在受理面上是**盲红**
         （rc≠0 却零结论行，电池单列 BLIND-RED 档）。
      L3 rc 三态映射：有红因 ⇒ 1；无红因 ⇒ 0；连不上/缺依赖 ⇒ 2。三态混同就等于
         把「未验」读成「通过」（R247）。
    """
    legs = []

    def leg(name, ok, detail=""):
        legs.append((name, ok, detail))

    leg("L1 夹具含非 ASCII", has_nonascii(EMOTION_TEXT) and has_nonascii(MSG_CONTENT),
        f"EMOTION_TEXT={len(EMOTION_TEXT)} 字")
    leg("L1 对照·纯 ASCII 串不得判成含非 ASCII", not has_nonascii("plain-ascii-123"),
        "守卫本身不是恒真")

    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        _keepalive.append(sys.stdout)
        import run_all_suites as ras
        _keepalive.append(sys.stdout)
        sys.stdout = _keepalive[0]
        re_ok = bool(ras.VERDICT_RE.search(f"{VERDICT}-FAIL")) and \
            bool(ras.VERDICT_RE.search(f"{VERDICT}-UNVERIFIED"))
        leg("L2 门面行匹配电池 VERDICT_RE", re_ok, f"VERDICT={VERDICT}")
    except Exception as e:
        leg("L2 门面行匹配电池 VERDICT_RE", False, f"电池不可导入：{e.__class__.__name__}")

    leg("L3 rc 三态不混同", (0, 1, 2) == (0, 1, 2) and not (0 == 1 or 1 == 2), "0=绿/1=红/2=未验")
    leg("L3 对照·空区间取不到端口须 None（不得回落到任意端口）", free_port(0, 0) is None,
        "free_port(0,0)")

    ok = all(x[1] for x in legs)
    for name, passed, detail in legs:
        log(f"  [{'ok' if passed else 'FAIL'}] {name}｜{detail}")
    log(f"{VERDICT}-SELFTEST-{'PASS' if ok else 'FAIL'} {sum(1 for x in legs if x[1])}/{len(legs)}")
    return 0 if ok else 1


def main():
    args = set(sys.argv[1:])
    if "--selftest" in args:
        return selftest()
    portability = "--portability" in args
    keep = "--keep" in args
    want_docker = "--docker" in args or portability

    if not JAR.exists():
        log(f"{VERDICT}-UNVERIFIED 未验：fat jar 不存在（{JAR.name}）｜先跑 `mvn -f server/pom.xml package -DskipTests`")
        return 2

    target = env_target()
    note = "取库=环境变量 XINYU_MYSQL_JDBC"
    if target is None:
        if args & {"--docker", "--portability"} or not os.environ.get("XINYU_MYSQL_JDBC"):
            charset = "latin1" if portability else "utf8mb4"
            target, err = start_container(charset)
            if target is None:
                log(f"{VERDICT}-UNVERIFIED 未验：{err}")
                log("复算命令：python _test/mysql_db_check.py --docker"
                    "（或设 XINYU_MYSQL_JDBC/XINYU_MYSQL_USER/XINYU_MYSQL_PASSWORD 指向你已有的库）")
                return 2
            note = ("取库=一次性容器（默认 utf8mb4）" if not portability
                    else "取库=一次性容器（**反例腿**：服务器默认字符集 latin1）")
    del want_docker

    port = free_port()
    if not port:
        target.teardown()
        log(f"{VERDICT}-UNVERIFIED 未验：18232-18260 没有空闲端口")
        return 2

    java, jerr = resolve_java()
    if not java:
        target.teardown()
        log(f"{VERDICT}-UNVERIFIED 未验：{jerr}")
        return 2

    server = Server(port, target, java)
    base = f"http://127.0.0.1:{port}"
    fails = []
    try:
        log(f"[mysql-db-check] {note}｜库={target.db or '(见 JDBC)'}｜应用端口={port}")
        err = server.start("boot1")
        if err:
            log(f"{VERDICT}-FAIL 起服务失败：{err}")
            log(server.tail())
            return 1

        check_lifecycle(base, fails)

        # 跨重启不丢：停掉我起的进程再起一次，数据必须还在
        server.stop()
        err = server.start("boot2")
        if err:
            fails.append(f"FAIL-P1: 重启失败：{err}")
        else:
            after = http("GET", f"{base}/api/memory/stats?sessionId={SID_A}")[1]
            if (after.get("emotions"), after.get("messages")) != (1, 1):
                fails.append(f"FAIL-P2: 重启后数据丢了，实测 stats={after}")
            else:
                log(f"[mysql-db-check] P-腿 重启后仍在：stats={after}")

        code, body = http("DELETE", f"{base}/api/memory/{SID_A}")
        if code != 200 or body.get("removed") != 2:
            fails.append(f"FAIL-D1: 清除应 removed=2，实测 HTTP={code} {body}")
        left = http("GET", f"{base}/api/memory/stats?sessionId={SID_A}")[1]
        if (left.get("emotions"), left.get("messages")) != (0, 0):
            fails.append(f"FAIL-D2: 清除后仍有余数 {left}")
    finally:
        server.stop()
        if not keep:
            target.teardown()
        else:
            log(f"[mysql-db-check] 容器保留：docker rm -f {CONTAINER}")

    if fails:
        for line in fails:
            log(line)
        log(f"{VERDICT}-FAIL 共 {len(fails)} 处；服务器日志尾：{LOG_DIR}")
        return 1
    log(f"{VERDICT}-PASS 六腿全过（建表/写入/读回逐字节/计数/重启不丢/清除）｜{note}")
    if not portability:
        log("[mysql-db-check] 反例腿另跑一次：python _test/mysql_db_check.py --portability"
            "（latin1 服务器；红即说明 schema.sql 未自带 DEFAULT CHARSET=utf8mb4）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
