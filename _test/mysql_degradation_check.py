# -*- coding: utf-8 -*-
"""MySQL 故障时的**运行期**优雅降级行为回执（r169）。

这条判据要回答的问题很具体：库挂掉的时候，客户端拿到的是什么？
  修前：`MemoryController` 全文零 DataAccessException 处理（grep @ExceptionHandler|ControllerAdvice
        在 server/src/main/java 下实测 0 命中），于是拿到的是 Spring 白标 500 ——
        「服务端持久面挂了」与「我这个请求写得不对」在响应上**完全同形**，
        前端既不能判断该不该退回本地存储，判据也没法断言降级是否发生。
  修后：`DbFailure` 六类归因 + `DatabaseFailureAdvice` 落成 503/409/504/403/422/500，
        带 ok=false / error / retryable / Retry-After。

为什么测**运行期**而不是启动期（这是本件口径的边界，不是偷懒）：Flyway 在启动期做迁移，
库不可达时应用**根本起不来**——那是「主存储不在，就不对外服务」的另一种正确姿势，
但它不是"降级"。所以本件先把服务起在真库上，再**把库拔掉**，测的是连接建立之后失效这一类：
连接被断、池借不到连接、查询超时。这几类恰好是 objective 点名的那三类里的两大类。

五条腿：
  D1 起在真库上：/api/health/db 回 UP、product=MySQL、两张表在位、列级字符集全 utf8mb4
  D2 拔掉库之后写：必须 503 + error=db-unavailable + retryable=true + Retry-After
  D3 拔掉库之后读：同样结构化 503（不许退化成白标 500 或空响应）
  D4 拔掉库之后 /api/health 仍回 UP：服务活着，死的是持久面 —— 两面必须可分离，
     否则「优雅降级」根本没有输入信号（前端靠这对读数决定回落本地存储）
  D5 /api/health/db 自己必须报 DOWN 且带错误类名，且**不许抛**（探测面自己不能成为故障源）

取库：复用 mysql_db_check 的本机 mysqld 一次性实例通道（无 Docker 也能跑）。
退出码：0=五腿全过 / 1=判红 / 2=环境未验（起不来实例或缺 jar/缺 JVM —— 不是绿）。
`--selftest` 只判本件的取数与判定链（不起进程不碰端口），可进回归电池整跑。
"""
import io
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
_keepalive = [sys.stdout]

ROOT = Path(__file__).resolve().parents[1]
JAR = ROOT / "server" / "target" / "soulisle-server.jar"
LOG_DIR = Path(os.environ.get("TEMP") or "/tmp") / "xinyu-mysql-degradation"
LOG_DIR.mkdir(parents=True, exist_ok=True)
VERDICT = "MYSQL-DEGRADATION"


def http(method, url, body=None, timeout=25):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.status, _maybe_json(raw), dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        return e.code, _maybe_json(raw), dict(e.headers)


def _maybe_json(raw):
    """响应体解析不判红：非 JSON（白标 HTML）时原样回传，由断言点名它。"""
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def port_free(port):
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", port)) != 0


class App:
    """起了就归我：只按自己记下的 PID 收尾，不按端口/名字找人。"""

    def __init__(self, java, port, jdbc):
        self.java, self.port, self.jdbc = java, port, jdbc
        self.proc, self.log = None, LOG_DIR / "app.log"

    def start(self, tag):
        env = dict(os.environ)
        env.update({
            "XINYU_DB_URL": self.jdbc,
            "XINYU_DB_DRIVER": "com.mysql.cj.jdbc.Driver",
            "XINYU_DB_USER": "root",
            "XINYU_DB_PASSWORD": "",
            "XINYU_PORT": str(self.port),
            # 故障注入腿要的是**快速失败**：把借连接预算压到 1.5s，否则一次拔掉库要等 5s
            # 才失败，而这条判据在电池里跑，等待预算就是它的墙钟成本。
            "XINYU_DB_CONNECTION_TIMEOUT_MS": "1500",
        })
        fh = open(self.log, "wb")
        self.proc = subprocess.Popen([self.java, "-jar", str(JAR)], cwd=str(ROOT), env=env,
                                     stdout=fh, stderr=subprocess.STDOUT)
        deadline = time.time() + 120
        while time.time() < deadline:
            if self.proc.poll() is not None:
                return "应用提前退出 rc=%s，见 %s" % (self.proc.returncode, self.log)
            try:
                code, _, _ = http("GET", "http://127.0.0.1:%d/api/health" % self.port, timeout=3)
                if code == 200:
                    return None
            except Exception:
                time.sleep(1.5)
        return "120s 内 /api/health 未就绪，见 %s" % self.log

    def tail(self, n=25):
        if self.log.exists():
            return "\n".join(self.log.read_text(encoding="utf-8", errors="replace").splitlines()[-n:])
        return "(无日志)"

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=25)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def pick_app_port(used):
    for p in range(18270, 18299):
        if p != used and port_free(p):
            return p
    return None


def selftest():
    """离线自证：本件的判定链有牙，且不会因为「拿不到读数」而被读成通过。"""
    legs = []

    def leg(name, ok, detail=""):
        legs.append((name, bool(ok), detail))

    leg("D2/D3 判据要求的是**结构化错误体**，白标 HTML 必须判不通过",
        _maybe_json("<html><body>Whitelabel Error Page</body></html>")
        == "<html><body>Whitelabel Error Page</body></html>")
    leg("JSON 响应正常解析（否则五腿都无从取字段）",
        _maybe_json('{"ok":false,"error":"db-unavailable"}') == {"ok": False, "error": "db-unavailable"})
    # 反例：把"服务活着"与"库活着"混成一个信号，这条判据就失去区分力 ⇒ 本件必须分两个端点取数
    leg("健康面分两面（/api/health 与 /api/health/db）——判据靠这对读数区分『服务活/库死』",
        "/api/health" != "/api/health/db")
    leg("故障注入的连接预算被显式收紧（1500ms），不靠 HikariCP 默认 30s",
        "XINYU_DB_CONNECTION_TIMEOUT_MS" in io.open(__file__, encoding="utf-8").read())
    leg("取库通道复用 mysql_db_check（禁另写一份 mysqld 启动逻辑）",
        "import mysql_db_check" in io.open(__file__, encoding="utf-8").read()
        or "mysql_db_check as m" in io.open(__file__, encoding="utf-8").read())
    leg("墙钟预算：单次 HTTP 超时 25s < 电池对单套件的容忍上限，且五腿串行可预期",
        "timeout=25" in io.open(__file__, encoding="utf-8").read())
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        _keepalive.append(sys.stdout)
        import run_all_suites as ras
        _keepalive.append(sys.stdout)
        sys.stdout = _keepalive[0]
        leg("门面行匹配电池 VERDICT_RE（认不出的套件在受理面上是盲红）",
            bool(ras.VERDICT_RE.search("%s-PASS" % VERDICT))
            and bool(ras.VERDICT_RE.search("%s-UNVERIFIED" % VERDICT)))
    except Exception as e:
        leg("门面行匹配电池 VERDICT_RE（认不出的套件在受理面上是盲红）", False, str(e))
    ok = sum(1 for x in legs if x[1])
    for name, passed, detail in legs:
        print("  [%s] %s%s" % ("ok" if passed else "FAIL", name, ("｜" + detail) if detail else ""),
              flush=True)
    print("%s-SELFTEST-%s %d/%d" % (VERDICT, "PASS" if ok == len(legs) else "FAIL", ok, len(legs)),
          flush=True)
    return 0 if ok == len(legs) else 1


def main():
    if "--selftest" in sys.argv[1:]:
        return selftest()
    if not JAR.exists():
        print("%s-UNVERIFIED 未验：fat jar 不存在（%s）｜先跑 `python _test/build_jar.py`"
              % (VERDICT, JAR.name), flush=True)
        return 2
    try:
        _keepalive.append(sys.stdout)
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import mysql_db_check as m
        _keepalive.append(sys.stdout)
        sys.stdout = _keepalive[0]
        java, jerr = m.resolve_java()
    except Exception as e:
        print("%s-UNVERIFIED 未验：取库/JVM 通道不可用（%s: %s）" % (VERDICT, e.__class__.__name__, e),
              flush=True)
        return 2
    if not java:
        print("%s-UNVERIFIED 未验：%s" % (VERDICT, jerr), flush=True)
        return 2

    target, err = m.start_local("utf8mb4")
    if target is None:
        print("%s-UNVERIFIED 未验：本机 mysqld 一次性实例起不来（%s）" % (VERDICT, err), flush=True)
        return 2
    db_port = m.LOCAL_PORTS["utf8mb4"]
    app_port = pick_app_port(db_port)
    if not app_port:
        target.teardown()
        print("%s-UNVERIFIED 未验：18270-18298 没有空闲应用端口" % VERDICT, flush=True)
        return 2

    jdbc = target.jdbc.replace("?serverTimezone", "?useSSL=false&serverTimezone")
    app = App(java, app_port, jdbc)
    fails = []
    base = "http://127.0.0.1:%d" % app_port
    try:
        print("[degradation-check] 库=%s:%d｜应用=%d" % ("127.0.0.1", db_port, app_port), flush=True)
        boot = app.start("boot")
        if boot:
            print("%s-UNVERIFIED 未验：应用起不来（%s）" % (VERDICT, boot), flush=True)
            print(app.tail(12), flush=True)
            return 2

        # ── D1 ──
        code, body, _ = http("GET", base + "/api/health/db")
        if code != 200:
            fails.append("FAIL-D1: /api/health/db HTTP=%s body=%r" % (code, body))
        else:
            if body.get("status") != "UP":
                fails.append("FAIL-D1: 库活着时 health/db 应为 UP，实测 %r" % body.get("status"))
            if "MySQL" not in str(body.get("product")):
                fails.append("FAIL-D1: product 应含 MySQL，实测 %r" % body.get("product"))
            tables = body.get("tables") or {}
            if tables.get("allPresent") is not True:
                fails.append("FAIL-D1: 两张表应在位，实测 missing=%r" % tables.get("missing"))
            charset = body.get("charset") or {}
            if charset.get("allUtf8mb4") is not True:
                fails.append("FAIL-D1: 列级字符集应全 utf8mb4，实测非 utf8mb4 列=%r"
                             % charset.get("nonUtf8mb4Columns"))
            pool = body.get("pool") or {}
            if pool.get("kind") != "hikari" or "active" not in pool:
                fails.append("FAIL-D1: 池水位应可读到活值，实测 %r" % pool)
            # 这两格是「连接配置」这条要求唯一的**运行时**证据：application.yml 里写了
            # maximum-pool-size/connection-timeout，只有从**跑起来的应用**里读回来，
            # 才证明 yml 的默认值与环境变量覆盖这两条通道都真的接上了池。
            # （只 grep 配置文件 = 测文本，不测接线；本仓既有教训「配置需行为回执」。）
            if pool.get("max") != 16:
                fails.append("FAIL-D1: yml 默认 maximum-pool-size=16 未落到运行时池，实测 %r"
                             % pool.get("max"))
            if pool.get("connectionTimeoutMs") != 1500:
                fails.append("FAIL-D1: 本件注入的 XINYU_DB_CONNECTION_TIMEOUT_MS=1500 未生效，实测 %r"
                             " ⇒ 环境变量到池这条链断了，故障时的快速回落也就不成立"
                             % pool.get("connectionTimeoutMs"))
            if pool.get("leakDetectionThresholdMs") != 20000:
                fails.append("FAIL-D1: yml 默认 leak-detection-threshold=20000 未落到运行时池，实测 %r"
                             % pool.get("leakDetectionThresholdMs"))

        # 先写一条数据，确认这条链本来可用（否则后面的 503 可能只是「本来就坏了」）
        sid = "degradation-%d" % int(time.time())
        code, body, _ = http("POST", base + "/api/memory/emotion",
                             {"sessionId": sid, "emotion": "joy", "intensity": 0.7,
                              "text": "降级判据夹具 中文 🌧️"})
        if code != 200 or not (isinstance(body, dict) and body.get("ok")):
            fails.append("FAIL-D0 前置：健康期写入未成功 HTTP=%s body=%r（后面的降级读数不成立）"
                         % (code, body))

        # ── 拔库 ──
        target.teardown()
        target = None
        deadline = time.time() + 40
        while time.time() < deadline and not port_free(db_port):
            time.sleep(1)
        if not port_free(db_port):
            fails.append("FAIL-前提: mysqld 端口 %d 40s 内没释放，故障注入没真发生" % db_port)
        else:
            print("[degradation-check] 库已拔掉（端口 %d 空闲）" % db_port, flush=True)
            # 池里的旧连接不会立刻感知到对端消失，第二次取连接才失败 ⇒ 先打一发再取判定读数
            http("GET", base + "/api/memory/stats?sessionId=%s" % sid)

            # ── D2 写 ──
            code, body, hdr = http("POST", base + "/api/memory/emotion",
                                   {"sessionId": sid, "emotion": "sad", "intensity": 0.2,
                                    "text": "拔库后应被拒"})
            if code != 503:
                fails.append("FAIL-D2: 拔库后写入应 503，实测 HTTP=%s body=%r" % (code, body))
            if not isinstance(body, dict) or body.get("error") != "db-unavailable":
                fails.append("FAIL-D2: 错误体应是结构化 db-unavailable，实测 %r" % (body,))
            elif body.get("retryable") is not True:
                fails.append("FAIL-D2: 连接类失败应标 retryable=true，实测 %r" % body)
            if hdr.get("Retry-After") != "2":
                fails.append("FAIL-D2: 应带 Retry-After: 2，实测头=%r" % hdr.get("Retry-After"))

            # ── D3 读 ──
            code, body, _ = http("GET", base + "/api/memory/stats?sessionId=%s" % sid)
            if code != 503 or not isinstance(body, dict) or body.get("ok") is not False:
                fails.append("FAIL-D3: 拔库后读取也应结构化 503，实测 HTTP=%s body=%r" % (code, body))

            # ── D4 服务面与库面必须可分离 ──
            code, body, _ = http("GET", base + "/api/health")
            if code != 200 or body.get("status") != "UP":
                fails.append("FAIL-D4: 库死不等于服务死，/api/health 应仍 UP，实测 HTTP=%s %r"
                             % (code, body))

            # ── D5 库面自证报 DOWN 且不抛 ──
            code, body, _ = http("GET", base + "/api/health/db")
            if code != 200:
                fails.append("FAIL-D5: 探测失败也要 200 带读数（不许把探测自身的失败抛成 5xx），实测 %s" % code)
            elif body.get("status") != "DOWN":
                fails.append("FAIL-D5: 库已拔，health/db 应 DOWN，实测 %r" % body.get("status"))
            elif not body.get("error"):
                fails.append("FAIL-D5: DOWN 必须带错误类名，供归因；实测 %r" % body)
    finally:
        app.stop()
        if target is not None:
            target.teardown()

    if fails:
        for f in fails:
            print(f, flush=True)
        print("%s-FAIL 共 %d 处｜应用日志尾：%s" % (VERDICT, len(fails), LOG_DIR), flush=True)
        return 1
    print("%s-PASS 五腿全过（库面自证/拔库后写/读/服务面分离/探测面不抛）" % VERDICT, flush=True)
    return 0


if __name__ == "__main__":
    # r173 兜底：未捕获异常必须留下具名结论行，否则电池只见 rc≠0（BLIND-RED）
    from check_instrument import install_excepthook
    install_excepthook("MYSQL-DEGRADATION")
    sys.exit(main())
