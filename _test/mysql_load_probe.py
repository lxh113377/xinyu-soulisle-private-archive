"""MySQL 索引设计与并发吞吐的**测量**回执（r169）。

跑法::

    python -B _test/mysql_load_probe.py               # 活体判定（三态 rc）
    python -B _test/mysql_load_probe.py --report      # 只出读数，不判定
    python -B _test/mysql_load_probe.py --selftest    # 离线：变换/解析/判定函数各配一条会红的反例
    python -B _test/mysql_load_probe.py --negative-control   # 活体反例腿：真计划塞对照位必须判红

为什么需要这一件：`memory/2026-10-13-r169-mysql.md` 第三节把「索引设计」写成「现状即正确」，
但那是**读代码读出来的论证**（V1 里有 `KEY idx_chat_message_session (session_id, id)`、
查询按 session 前缀 + id 倒序 + LIMIT），本机一次都没量过。目标原文要求
「优化性能以应对高并发与大数据量场景」——**不量就没有资格说"够"**。
本件把同一批数据灌进两张表（一张按迁移产物原样建、一张机械地摘掉那行 `KEY`），
用服务层那条热查询形态各跑一遍，读 EXPLAIN 计划、单查询净耗时、并发吞吐。

夹具的 DDL 一律由**迁移产物本身**派生（`V1__j4_baseline_schema.sql` 逐字执行后改名），
对照表由机械变换得出 —— 手抄一份"理想表"就是在测自己造的假对象。

取库只走**一次性实例**（本机 MySQL 8.4 二进制，端口 13307），绝不碰开发态 3306：
06-constraints 的 env_mode 红线 + 别人正在用那个实例。
"""

import hashlib
import json
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "server" / "src" / "main" / "resources" / "db" / "migration"
             / "V1__j4_baseline_schema.sql")
VERDICT = "MYSQL-LOAD"

# 一次性实例里的库名（main 里从 mysql_db_check 取，保持两侧同源）
DB = ""

ROWS = 200 * 300           # 200 个会话 × 每会话 300 条
SESSIONS = 200
PER_SESSION = 300
HIT_SESSION = "load-s-007"
TOP = 200                  # 与 MemoryService.normLimit 的缺省值同量级
CONC_CLIENTS = 12          # 刻意 < 池上限 16：这一腿量的是库面，不是池面
CONC_PER_CLIENT = 15


def q(mysql_bin, port, sql, timeout=300):
    """跑一条 SQL，返回 (rc, stdout, stderr)。

    ⚠️ 必须带库名：`mysql -e` 不带 database 参数时对任何非限定语句都以
    `ERROR 1046 No database selected` 收口（r169 首跑实测，红因看着像「表不存在」其实是没选库）。

    ⚠️ SQL 走 **stdin** 而不是 `-e` 参数：Windows 的 CreateProcess 命令行上限约 32 KB，
    500 行/语句的批量 INSERT 一超就 `[WinError 206] 文件名或扩展名太长`
    （r169 把 created_at 换成确定性表达式后当场踩中 —— 每行多约 45 字节就够顶穿）。
    """
    args = [str(mysql_bin), "--no-defaults", "-h127.0.0.1", "-P%d" % port, "-uroot",
            "--default-character-set=utf8mb4", "-N", "-B"]
    if DB:
        args.append(DB)
    p = subprocess.run(args, input=sql.encode("utf-8"), capture_output=True, timeout=timeout)
    return (p.returncode,
            p.stdout.decode("utf-8", "replace"),
            p.stderr.decode("utf-8", "replace"))


def shipped_create():
    """从迁移产物里取出 chat_message 的建表语句原文（含结尾分号）。"""
    text = MIGRATION.read_text(encoding="utf-8")
    start = text.index("CREATE TABLE IF NOT EXISTS chat_message")
    end = text.index(";", start) + 1
    return text[start:end]


def strip_key(stmt):
    """机械变换：只删掉表内 `KEY idx_...` 那一行，返回 (新 DDL, 被删的行)。

    两道自证缺一不可：**恰好一行**（删到 PRIMARY KEY 或删两行 ⇒ 对照面不再是「少一个二级索引」），
    以及删完**不能有悬空逗号**（上一行以 `,` 结尾而它的下一行被删掉 ⇒ MySQL 报 1064，
    r169 预演实测）。
    """
    lines = stmt.splitlines(keepends=True)
    hits = [i for i, ln in enumerate(lines) if ln.strip().startswith("KEY idx_")]
    if len(hits) != 1:
        raise AssertionError("表内 KEY idx_ 行应恰好 1 行，实测 %d 行" % len(hits))
    removed = lines.pop(hits[0])
    prev = lines[hits[0] - 1]
    body = prev.rstrip("\r\n")
    if body.rstrip().endswith(","):
        nl = "\r\n" if prev.endswith("\r\n") else "\n"
        lines[hits[0] - 1] = body.rstrip()[:-1] + nl
    out = "".join(lines)
    if "KEY idx_" in out or "PRIMARY KEY" not in out:
        raise AssertionError("变换后仍含 KEY idx_，或把 PRIMARY KEY 一起删了")
    return out, removed


QUERY = ("SELECT id, role, content, created_at FROM {t} "
         "WHERE session_id = '{sid}' ORDER BY id DESC LIMIT %d" % TOP)


def create_tables(mysql_bin, port):
    base = shipped_create()
    ddl_indexed = base.replace("chat_message", "lp_indexed")
    plain, _ = strip_key(base)
    ddl_plain = plain.replace("chat_message", "lp_plain")
    for name, ddl in (("lp_indexed", ddl_indexed), ("lp_plain", ddl_plain)):
        rc, _o, err = q(mysql_bin, port, "DROP TABLE IF EXISTS %s" % name)
        if rc != 0:
            return None, "DROP %s 失败 rc=%s：%s" % (name, rc, err.strip()[:200])
        rc, _o, err = q(mysql_bin, port, ddl)
        if rc != 0:
            return None, "建 %s 失败 rc=%s：%s" % (name, rc, err.strip()[:200])
    return {"indexed": ddl_indexed, "plain": ddl_plain}, None


def seed(mysql_bin, port):
    """两表灌**同一批**数据（逐字节相同 ⇒ 两侧读数可比）。批量 INSERT，500 行/语句。

    ⚠️ `created_at` 必须写成**确定性表达式**而不是 `CURRENT_TIMESTAMP`：
    第一版用 CURRENT_TIMESTAMP，L5「两侧结果集逐字节相等」当场判红 —— 两张表是分两条语句灌的，
    各自的时间戳本来就不同，跟索引一点关系没有。这种红如果靠**放宽断言**去消（改成只比 id），
    就等于把判据缺陷记成数据缺陷；正解是让夹具本身可比（同一条 lesson：先证判据再动数据）。
    """
    batch = []
    for i in range(ROWS):
        sid = "load-s-%03d" % (i % SESSIONS)
        # id 从 1 起：AUTO_INCREMENT 列写 0 会被 MySQL 当成「取下一个值」（除非会话带
        # NO_AUTO_VALUE_ON_ZERO），于是显式 id=0 那行实际拿到 1，与下一批的 id=1 撞主键 ——
        # ERROR 1062 Duplicate entry '1'（r169 首跑实测，看着像夹具写重了）。
        batch.append("(%d,'%s','user','内容 %d',TIMESTAMPADD(SECOND,%d,'2026-01-01 00:00:00'))"
                     % (i + 1, sid, i, i))
    for t in ("lp_indexed", "lp_plain"):
        head = "INSERT INTO %s (id, session_id, role, content, created_at) VALUES " % t
        for j in range(0, len(batch), 500):
            rc, _o, err = q(mysql_bin, port, head + ",".join(batch[j:j + 500]), timeout=600)
            if rc != 0:
                return "播种 %s 失败 rc=%s：%s" % (t, rc, err.strip()[:200])
    rc, out, err = q(mysql_bin, port,
                     "SELECT (SELECT COUNT(*) FROM lp_indexed), (SELECT COUNT(*) FROM lp_plain)")
    if rc != 0:
        return "计数读取失败 rc=%s：%s" % (rc, err.strip()[:200])
    got = out.strip().split()
    if got != [str(ROWS), str(ROWS)]:
        return "两表行数应各为 %d，实测 %s" % (ROWS, out.strip())
    return None


def parse_plan(line):
    """MySQL 8 经典 EXPLAIN 的 12 列 → 命名字典。列数不符一律报错，不猜。"""
    f = line.split("\t")
    if len(f) != 12:
        raise AssertionError("EXPLAIN 列数应为 12，实测 %d：%r" % (len(f), f))
    return {"type": f[4], "possible_keys": f[5], "key": f[6], "key_len": f[7],
            "rows": f[9], "filtered": f[10], "extra": f[11]}


def explain(mysql_bin, port, table):
    rc, out, err = q(mysql_bin, port, "EXPLAIN " + QUERY.format(t=table, sid=HIT_SESSION))
    if rc != 0:
        return None, "EXPLAIN %s 失败 rc=%s：%s" % (table, rc, err.strip()[:200])
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if len(lines) != 1:
        return None, "EXPLAIN %s 应恰好 1 行，实测 %d 行" % (table, len(lines))
    try:
        return parse_plan(lines[0]), None
    except AssertionError as e:
        return None, str(e)


def per_query_ms(mysql_bin, port, table, reps=3):
    """单查询净耗时：同一条查询在一**个**客户端会话里跑 k 次，取 (T_hi − T_lo)/(k_hi − k_lo)。

    为什么不能直接用 `mysql -e` 的墙钟：那里面包着约 27ms 的客户端启动常数（本机实测），
    有索引的一侧净耗时远小于它 —— 拿总墙钟比就是拿启动开销比，两侧差值会被常数压平。
    两点求斜率把常数项消掉，读到的才是查询本身。
    """
    sql = ";".join([QUERY.format(t=table, sid=HIT_SESSION)] * 25)
    short = ";".join([QUERY.format(t=table, sid=HIT_SESSION)] * 5)

    def wall(text):
        t0 = time.perf_counter()
        rc, _o, err = q(mysql_bin, port, text, timeout=600)
        dt = time.perf_counter() - t0
        if rc != 0:
            return None, "计时 %s 失败 rc=%s：%s" % (table, rc, err.strip()[:200])
        return dt, None

    runs_hi, runs_lo = [], []
    for _ in range(reps):
        d_hi, why = wall(sql)
        if d_hi is None:
            return None, why
        d_lo, why = wall(short)
        if d_lo is None:
            return None, why
        runs_hi.append(d_hi)
        runs_lo.append(d_lo)
    net = (statistics.median(runs_hi) - statistics.median(runs_lo)) / 20.0 * 1000.0
    return {"per_query_ms": round(net, 3),
            "wall25_ms": round(statistics.median(runs_hi) * 1000, 1),
            "wall5_ms": round(statistics.median(runs_lo) * 1000, 1)}, None


def result_digest(mysql_bin, port, table):
    """把结果集逐字节哈希 —— 索引只许改访问路径，不许改语义。"""
    rc, out, err = q(mysql_bin, port, QUERY.format(t=table, sid=HIT_SESSION))
    if rc != 0:
        return None, "取结果 %s 失败 rc=%s：%s" % (table, rc, err.strip()[:200])
    n = len([ln for ln in out.splitlines() if ln.strip()])
    return {"rows": n, "sha256": hashlib.sha256(out.encode("utf-8")).hexdigest()[:16]}, None


def table_index_bytes(mysql_bin, port):
    rc, out, err = q(mysql_bin, port,
                     "SELECT TABLE_NAME, ENGINE, TABLE_ROWS, DATA_LENGTH, INDEX_LENGTH "
                     "FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() "
                     "AND TABLE_NAME IN ('lp_indexed','lp_plain') ORDER BY TABLE_NAME")
    if rc != 0:
        return None, "读表尺寸失败 rc=%s：%s" % (rc, err.strip()[:200])
    got = {}
    for ln in out.splitlines():
        f = ln.split("\t")
        if len(f) == 5:
            got[f[0]] = {"engine": f[1], "rows": int(f[2]), "data_bytes": int(f[3]),
                         "index_bytes": int(f[4])}
    return got, None


def concurrency(mysql_bin, port, clients=CONC_CLIENTS, per_client=CONC_PER_CLIENT):
    """C 个客户端并发跑热查询：读吞吐、错误数、每个客户端拿到的行数是否一致。"""
    errors, row_counts = [], []
    lock = threading.Lock()
    sql = QUERY.format(t="lp_indexed", sid=HIT_SESSION)

    def worker(idx):
        local_rows = []
        for _ in range(per_client):
            try:
                rc, o, e = q(mysql_bin, port, sql, timeout=120)
                if rc != 0:
                    with lock:
                        errors.append("client%s rc=%s %s" % (idx, rc, e.strip()[:80]))
                else:
                    local_rows.append(len([ln for ln in o.splitlines() if ln.strip()]))
            except Exception as ex:
                with lock:
                    errors.append("client%s %s: %s" % (idx, ex.__class__.__name__, ex))
        with lock:
            row_counts.append(local_rows)

    t0 = time.perf_counter()
    ths = [threading.Thread(target=worker, args=(i,)) for i in range(clients)]
    for th in ths:
        th.start()
    for th in ths:
        th.join()
    wall = time.perf_counter() - t0
    done = sum(len(x) for x in row_counts)
    flat = sorted({n for x in row_counts for n in x})
    return {"clients": clients, "per_client": per_client, "expected_total": clients * per_client,
            "completed": done, "errors": len(errors), "error_sample": errors[:3],
            "wall_s": round(wall, 2),
            "qps": round(done / wall, 1) if wall > 0 else None,
            "distinct_row_counts": flat,
            "clients_that_ran": sum(1 for x in row_counts if x)}


def judge(m):
    """把读数折成 fails；纯函数，好让 --selftest 能喂合成读数逼它翻红（不靠真库）。

    期望全部来自本机实测形态，不是先验猜的：
    有索引侧 `type=ref` + `key=idx_*` + `extra=Backward index scan`（无 filesort），
    摘掉索引侧 `possible_keys=NULL` + `type=index`（退化成主键全扫）。
    """
    fails = []
    plan_i, plan_p = m.get("plan_indexed"), m.get("plan_plain")
    if not isinstance(plan_i, dict) or not isinstance(plan_p, dict):
        return ["FAIL-L1: EXPLAIN 读数缺失/畸形（%r / %r）" % (plan_i, plan_p)]

    # L1 有索引侧确实走了那条 KEY，且不做 filesort
    if plan_i["type"] != "ref":
        fails.append("FAIL-L1: 有索引侧 type 应为 ref，实测 %r" % plan_i["type"])
    if not plan_i["key"].startswith("idx_"):
        fails.append("FAIL-L1: 有索引侧 key 应为 idx_*，实测 %r" % plan_i["key"])
    if "filesort" in plan_i["extra"].lower():
        fails.append("FAIL-L1: 有索引侧不应出现 filesort，实测 extra=%r" % plan_i["extra"])

    # L2 对照侧必须真的没索引可用 —— 否则整件只是在拿两张都有索引的表比，读数没有对照力
    if plan_p["possible_keys"] != "NULL":
        fails.append("FAIL-L2: 对照侧 possible_keys 应为 NULL（无可用索引），实测 %r"
                     % plan_p["possible_keys"])
    if plan_p["type"] == "ref":
        fails.append("FAIL-L2: 对照侧不应仍走 ref，实测 type=%r ⇒ 摘 KEY 的变换没生效" % plan_p["type"])

    # L3 information_schema 的索引字节数是独立第二通道（不看计划，只看物理）
    tb = m.get("tables") or {}
    if not tb.get("lp_indexed") or tb.get("lp_indexed", {}).get("index_bytes", 0) <= 0:
        fails.append("FAIL-L3: lp_indexed 的 INDEX_LENGTH 应 > 0，实测 %r" % tb.get("lp_indexed"))
    if tb.get("lp_plain") and tb["lp_plain"]["index_bytes"] != 0:
        fails.append("FAIL-L3: 对照表 lp_plain 的 INDEX_LENGTH 应为 0，实测 %r" % tb["lp_plain"])
    for t in ("lp_indexed", "lp_plain"):
        if tb.get(t) and tb[t]["engine"] != "InnoDB":
            fails.append("FAIL-L3: %s 引擎应为 InnoDB（事务/回滚靠它），实测 %r" % (t, tb[t]["engine"]))

    # L4 净耗时：两侧都量到才算，比值取实测下界 2×
    ti, tp = m.get("time_indexed") or {}, m.get("time_plain") or {}
    ni, np_ = ti.get("per_query_ms"), tp.get("per_query_ms")
    if ni is None or np_ is None:
        fails.append("FAIL-L4: 单查询净耗时取不到（%r / %r）" % (ti, tp))
    elif ni <= 0:
        fails.append("FAIL-L4: 有索引侧净耗时 %s ms ≤ 0 ⇒ 分辨率不够（两点求斜率被噪声吃掉），"
                     "本腿判未验不判绿" % ni)
    elif np_ < ni * 2:
        fails.append("FAIL-L4: 摘掉索引后单查询净耗时应至少翻倍，实测 有索引 %s ms / 对照 %s ms"
                     % (ni, np_))

    # L5 语义不变：索引只改访问路径，不许改结果
    di, dp = m.get("digest_indexed") or {}, m.get("digest_plain") or {}
    if not di or not dp:
        fails.append("FAIL-L5: 结果集摘要缺失")
    elif di.get("sha256") != dp.get("sha256") or di.get("rows") != dp.get("rows"):
        fails.append("FAIL-L5: 两侧结果集不逐字节相等（索引不该改变语义）%r vs %r" % (di, dp))
    elif di.get("rows") != TOP:
        fails.append("FAIL-L5: 命中会话应有 %d 行，实测 %r" % (TOP, di.get("rows")))

    # L6 并发腿：0 错误 + 每个客户端都真的跑了 + 各客户端行数一致
    c = m.get("concurrency") or {}
    if c.get("errors"):
        fails.append("FAIL-L6: 并发腿有 %s 个错误，样本 %s" % (c["errors"], c.get("error_sample")))
    if c.get("completed") != c.get("expected_total"):
        fails.append("FAIL-L6: 并发完成数应为 %s，实测 %s ⇒ 有客户端整轮没跑成"
                     % (c.get("expected_total"), c.get("completed")))
    if c.get("clients_that_ran") != c.get("clients"):
        fails.append("FAIL-L6: %s 个客户端应全部有产出，实测只有 %s 个"
                     % (c.get("clients"), c.get("clients_that_ran")))
    if c.get("distinct_row_counts") != [TOP]:
        fails.append("FAIL-L6: 并发下每个客户端应各拿 %d 行，实测行数值集 %s"
                     % (TOP, c.get("distinct_row_counts")))
    return fails


def face(m):
    """读数门面行：判绿时也把关键量印出来，别让「PASS」代替证据。"""
    ti = (m.get("time_indexed") or {}).get("per_query_ms")
    tp = (m.get("time_plain") or {}).get("per_query_ms")
    c = m.get("concurrency") or {}
    pi = m.get("plan_indexed") or {}
    pp = m.get("plan_plain") or {}
    return ("有索引 type=%s key=%s extra=%r｜对照 type=%s possible_keys=%s｜"
            "净耗时 %s ms vs %s ms｜并发 %s 客户端×%s 共 %s 次 %s s，qps=%s 错误=%s｜"
            "数据量 %s 行×2 表"
            % (pi.get("type"), pi.get("key"), pi.get("extra"),
               pp.get("type"), pp.get("possible_keys"), ti, tp,
               c.get("clients"), c.get("per_client"), c.get("completed"),
               c.get("wall_s"), c.get("qps"), c.get("errors"), ROWS))


def measure(mysql_bin, port):
    m = {}
    for key, table in (("plan_indexed", "lp_indexed"), ("plan_plain", "lp_plain")):
        val, err = explain(mysql_bin, port, table)
        m[key] = val if val else err
    for key, table in (("time_indexed", "lp_indexed"), ("time_plain", "lp_plain")):
        val, err = per_query_ms(mysql_bin, port, table)
        m[key] = val if val else err
    for key, table in (("digest_indexed", "lp_indexed"), ("digest_plain", "lp_plain")):
        val, err = result_digest(mysql_bin, port, table)
        m[key] = val if val else err
    tb, err = table_index_bytes(mysql_bin, port)
    m["tables"] = tb if tb else err
    m["concurrency"] = concurrency(mysql_bin, port)
    return m


def selftest():
    """离线自证：判定函数必须有牙，取数与变换必须会红。不连库。"""
    bad = []
    good = {
        "plan_indexed": {"type": "ref", "possible_keys": "idx_lp_indexed_session",
                         "key": "idx_lp_indexed_session", "key_len": "258", "rows": "300",
                         "filtered": "100.00", "extra": "Backward index scan"},
        "plan_plain": {"type": "index", "possible_keys": "NULL", "key": "PRIMARY",
                       "key_len": "8", "rows": "200", "filtered": "10.00",
                       "extra": "Using where; Backward index scan"},
        "tables": {"lp_indexed": {"engine": "InnoDB", "rows": ROWS, "data_bytes": 16384,
                                  "index_bytes": 16384},
                   "lp_plain": {"engine": "InnoDB", "rows": ROWS, "data_bytes": 16384,
                                "index_bytes": 0}},
        "time_indexed": {"per_query_ms": 0.9},
        "time_plain": {"per_query_ms": 12.4},
        "digest_indexed": {"rows": TOP, "sha256": "deadbeefdeadbeef"},
        "digest_plain": {"rows": TOP, "sha256": "deadbeefdeadbeef"},
        "concurrency": {"clients": CONC_CLIENTS, "per_client": CONC_PER_CLIENT,
                        "expected_total": CONC_CLIENTS * CONC_PER_CLIENT,
                        "completed": CONC_CLIENTS * CONC_PER_CLIENT, "errors": 0,
                        "clients_that_ran": CONC_CLIENTS, "distinct_row_counts": [TOP],
                        "wall_s": 0.65, "qps": 278.1},
    }
    import copy

    def check(label, cond):
        if cond:
            return True
        bad.append(label)
        return False

    check("S0 正例（本机实测形态）应判绿：%s" % judge(copy.deepcopy(good)), not judge(good))

    # S1 把对照侧改成「也有索引」⇒ L2 必须咬（这条腿测的就是这张表）
    m = copy.deepcopy(good)
    m["plan_plain"] = dict(m["plan_plain"], possible_keys="idx_x", type="ref")
    r = judge(m)
    check("S1 对照侧仍有索引时未被 L2 拦下：%s" % r, any("FAIL-L2" in x for x in r))

    # S2 有索引侧退化出 filesort ⇒ L1 必须咬
    m = copy.deepcopy(good)
    m["plan_indexed"] = dict(m["plan_indexed"], extra="Using filesort")
    r = judge(m)
    check("S2 有索引侧出现 filesort 时未被 L1 拦下：%s" % r, any("FAIL-L1" in x for x in r))

    # S3 净耗时反过来（索引反而更慢）⇒ L4 必须咬
    m = copy.deepcopy(good)
    m["time_indexed"] = {"per_query_ms": 12.4}
    m["time_plain"] = {"per_query_ms": 0.9}
    r = judge(m)
    check("S3 净耗时倒挂时未被 L4 拦下：%s" % r, any("FAIL-L4" in x for x in r))

    # S4 净耗时取不到（0）⇒ 不许折成绿，也不许当"没索引更快"判红：必须是未验性质的点名
    m = copy.deepcopy(good)
    m["time_indexed"] = {"per_query_ms": 0}
    r = judge(m)
    check("S4 净耗时为 0 时没被点名（分辨率不足不许沉默）：%s" % r,
          any("分辨率不够" in x for x in r))

    # S5 结果集摘要不一致 ⇒ L5 必须咬（索引改了语义就是建错表）
    m = copy.deepcopy(good)
    m["digest_plain"] = {"rows": TOP, "sha256": "0000000000000000"}
    r = judge(m)
    check("S5 两侧结果集不等时未被 L5 拦下：%s" % r, any("FAIL-L5" in x for x in r))

    # S6 并发腿「有一个客户端整轮没跑成」⇒ 完成数/出场数都必须咬
    m = copy.deepcopy(good)
    m["concurrency"] = dict(m["concurrency"], completed=CONC_CLIENTS * CONC_PER_CLIENT - 1,
                            clients_that_ran=CONC_CLIENTS - 1)
    r = judge(m)
    check("S6 并发少跑一个客户端时没被点名：%s" % r,
          any("FAIL-L6" in x for x in r) and any("整轮没跑成" in x or "全部有产出" in x for x in r))

    # S7 机械变换：恰好删一行、结果不含 KEY idx_、且不留悬空逗号
    base = shipped_create()
    plain, removed = strip_key(base)
    check("S7 变换后仍含 KEY idx_", "KEY idx_" not in plain)
    check("S7 变换删的行数不等于 1（原 %d 行 → 现 %d 行）"
          % (len(base.splitlines()), len(plain.splitlines())),
          len(plain.splitlines()) == len(base.splitlines()) - 1)
    check("S7 变换后出现悬空逗号（PRIMARY KEY 行尾带 , 而下一行被删）",
          "),\r\n)" not in plain and "),\n)" not in plain)
    check("S7 被删的行不是 KEY idx_*：%r" % removed, removed.strip().startswith("KEY idx_"))
    check("S8 迁移产物本身不含 InnoDB/utf8mb4 条款（夹具源已漂）",
          "ENGINE=InnoDB" in base and "utf8mb4" in base)

    # S9 变换的反例：两张 KEY 行的 DDL 必须报错（否则"恰好一行"这道自证是恒真）
    two = base.replace("  KEY idx_chat_message_session (session_id, id)",
                       "  KEY idx_a (session_id),\n  KEY idx_b (role)")
    try:
        strip_key(two)
        bad.append("S9 两行 KEY 的 DDL 竟然没让变换报错（前置条件没被真正校验）")
    except AssertionError:
        pass

    # S10 计划解析器：11 列必须报错（否则列错位会把 extra 读成 key 还照样判绿）
    line12 = "\t".join(["1", "SIMPLE", "lp_plain", "NULL", "index", "NULL", "PRIMARY",
                        "8", "NULL", "200", "10.00", "Using where"])
    check("S10 12 列计划解析失败", parse_plan(line12)["key"] == "PRIMARY")
    try:
        parse_plan("\t".join(["1"] * 11))
        bad.append("S10 11 列计划没被拒（列错位会被读成正常计划）")
    except AssertionError:
        pass

    print("SELFTEST-PASS: 判定函数 6 条变异腿 + 变换/解析 4 条前置腿均按预期咬人"
          if not bad else "SELFTEST-FAIL: " + "; ".join(bad), flush=True)
    return 1 if bad else 0


def main():
    global DB
    mode = sys.argv[1:]
    if "--selftest" in mode:
        return selftest()
    try:
        _keepalive.append(sys.stdout)
        import mysql_db_check as m
        _keepalive.append(sys.stdout)
        sys.stdout = _keepalive[0]
    except Exception as e:
        print("%s-UNVERIFIED 未验：无法复用 mysql_db_check 的取库通道（%s: %s）"
              % (VERDICT, e.__class__.__name__, e), flush=True)
        return 2
    DB = m.LOCAL_DB
    mysql_bin = m.local_bin("mysql")
    if not mysql_bin:
        print("%s-UNVERIFIED 未验：本机缺 mysql.exe（basedir=%s，可设 XINYU_MYSQL_BASEDIR）"
              % (VERDICT, m.LOCAL_BASEDIR), flush=True)
        return 2
    target, err = m.start_local("utf8mb4")
    if target is None:
        print("%s-UNVERIFIED 未验：一次性实例起不来（%s）" % (VERDICT, err), flush=True)
        return 2
    port = m.LOCAL_PORTS["utf8mb4"]
    try:
        rc, _o, _e = q(mysql_bin, port, "SELECT 1")
        if rc != 0:
            print("%s-UNVERIFIED 未验：实例端口 %s 连不上（rc=%s）" % (VERDICT, port, rc), flush=True)
            return 2
        made, why = create_tables(mysql_bin, port)
        if made is None:
            print("%s-FAIL 建表：%s" % (VERDICT, why), flush=True)
            return 1
        why = seed(mysql_bin, port)
        if why:
            print("%s-FAIL 播种：%s" % (VERDICT, why), flush=True)
            return 1
        m2 = measure(mysql_bin, port)
        if "--negative-control" in mode:
            # 活体反例腿：把**真库真优化器**给出的「有索引计划」塞到对照位上，
            # judge 必须报 FAIL-L2。S1 那条用的是我手抄的合成计划 —— 抄来的计划能咬，
            # 只证明比较器有牙；真优化器给的计划能咬，才证明这条腿测的是 MySQL 的行为。
            live_indexed_plan, why = explain(mysql_bin, port, "lp_indexed")
            if not live_indexed_plan:
                print("%s-UNVERIFIED 未验：取不到 lp_indexed 的真计划（%s）" % (VERDICT, why), flush=True)
                return 2
            poisoned = dict(m2, plan_plain=live_indexed_plan)
            got = judge(poisoned)
            # 期望形态由**实测**定：真计划塞进对照位会把 L2 的两个子判据同时打翻
            # （possible_keys 非 NULL ∧ type=ref），所以这里要的是「红且只红在 L2 上」，
            # 不是「恰好一条」—— 我第一版写「恰好 1 条」，当场被自己的读数否证（实测 2 条）。
            if got and all("FAIL-L2" in x for x in got):
                print("NEG-PASS: 对照位换成真库的有索引计划后当场判红 %d 条（全部点名 L2）—— %s"
                      % (len(got), got[0]), flush=True)
                return 0
            print("NEG-FAIL: 期望红因全部落在 L2，实测 %d 条：%s" % (len(got), got), flush=True)
            return 1
        if "--report" in mode:
            print(json.dumps(m2, ensure_ascii=False, indent=2), flush=True)
            return 0
        fails = judge(m2)
        print("[load-probe] %s" % face(m2), flush=True)
        if "--json" in mode:
            print(json.dumps(m2, ensure_ascii=False, indent=2), flush=True)
        if fails:
            for f in fails:
                print("  %s" % f, flush=True)
            print("%s-FAIL 共 %d 处" % (VERDICT, len(fails)), flush=True)
            return 1
        print("%s-PASS 六腿全过（计划/对照/物理/净耗时/语义/并发）｜读数见门面行" % VERDICT, flush=True)
        return 0
    finally:
        target.teardown()


_keepalive = []


if __name__ == "__main__":
    sys.exit(main())
