# -*- coding: utf-8 -*-
"""备份 → 载回 → 断言一致：把「数据可恢复」从一句规程变成一次真演练（r169）。

为什么必须是演练而不是文档：备份只有在**被载回并断言过**之后才算备份。一份没人恢复过的
mysqldump 与「数据会丢」在故障现场是等价的（字符集把中文吃掉的 dump、只 dump 出一半表的
dump、参数漏了 --single-transaction 而在 InnoDB 上拿到跨时间点的半成品，全都长得像成功）。
本件按 备份 → 删库 → 恢复 → 逐字节比对 走一遍，中间任何一步不成立就判红，不写「建议定期备份」。

四条腿：
  B1 备份：mysqldump --single-transaction 取一致性快照，产物**非空**且两张表与夹具标记都在
  B2 破坏：DROP DATABASE（只允许打在**本件自己起的**一次性实例上，见下面的安全闸）
  B3 恢复：把 B1 的产物原样灌回
  B4 对账：逐表计数相等 + 中文/emoji/引号/反斜杠/制表**逐字节**相等 + 索引仍在 + 表 collation 仍是 utf8mb4

安全闸（这是本件最重要的一段）：B2 是不可逆动作。默认只允许打在
  · 本件用 --local 起的一次性实例（端口 13307/13308、库名 xinyu_check），或
  · 显式设 XINYU_BACKUP_ALLOW_DESTRUCTIVE=1 的环境变量目标。
其余一律判 UNVERIFIED 并说明拦在哪。本机 3306 那个是开发态实例（数据在 D:\\xinyu_mysql），
拿它演练等于删掉别人的库——那种"通过"比不跑更坏。

用法：
  python _test/mysql_backup_drill.py              # 起一次性实例并跑四条腿
  python _test/mysql_backup_drill.py --selftest   # 离线自证（进回归电池的常驻腿，不碰任何库）
退出码：0=全过 / 1=判红 / 2=未验（缺 mysqldump 或安全闸拦下，**不是绿**）。
"""
import io
import os
import re
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_test"))

VERDICT = "MYSQL-BACKUP"
SCRATCH_PORTS = {13307, 13308}       # mysql_db_check 的两个一次性实例端口
SCRATCH_DB = "xinyu_check"
DUMP_DIR = Path(os.environ.get("TEMP") or "/tmp") / "xinyu-mysql-backup-drill"
DUMP_DIR.mkdir(parents=True, exist_ok=True)

# 见 selftest() 里的注释：导入电池时**两个** stdout 包装器都要挂在这个名单上才不会被回收关掉 buffer。
_keepalive = []

# 与 mysql_db_check 同一组夹具形态：中文 + emoji + 引号 + 反斜杠 + 制表。
# 任一处被字符集或 dump 转义吃掉，B4 的逐字节比对就会红。
FIXTURES = [
    ("s1", "user", "今天下雨了，但我心里是晴的。emoji 也无损：🌧️→☀️"),
    ("s1", "assistant", "第一行中文\n第二行：单引号'双引号\"反斜杠\\ 制表\t结束 🌧️"),
    ("s2", "user", "另一会话的数据，恢复后必须还在"),
]
EMOTION_FIXTURES = [("s1", "joy", 0.82, "surprise", "陪聊第一幕 · 星雾点亮"),
                    ("s2", "sadness", 0.35, None, "下雨天 ️ 但没关系")]

# B1 的 dump 参数：--single-transaction 是 InnoDB 一致性快照的唯一来源（不加=非锁一致性，
# 备份期间有写入就拿到跨时间点的半成品）；--default-character-set=utf8mb4 保证 dump 里
# 的中文不是问号串；--routines/--events 当前库里没有存储过程，带着是为将来加了不被漏掉。
DUMP_ARGS = ["--single-transaction", "--default-character-set=utf8mb4",
             "--add-drop-database", "--databases", "--routines", "--events",
             "--set-charset", "--hex-blob"]


def cli_list(binary, port, db="", extra=()):
    return [str(binary), "--no-defaults", "-h127.0.0.1", "-P%d" % port, "-uroot",
            "--default-character-set=utf8mb4"] + list(extra) + ([db] if db else [])


def q(mysqld_bin, port, sql, out_fmt="-N"):
    """跑一条查询并返回 (rc, stdout)。取数一律带库名，DATABASE() 在无库的会话里是 NULL。"""
    p = subprocess.run(cli_list(mysqld_bin, port, SCRATCH_DB, [out_fmt, "-e", sql]),
                       capture_output=True, timeout=120)
    return p.returncode, ((p.stdout or b"").decode("utf-8", "replace")
                          + (p.stderr or b"").decode("utf-8", "replace")).strip()


def selftest():
    """离线自证：只钉「本件的取数与判定链」，不依赖 MySQL 是否在跑。

    四条各防一种静默失效：参数表被人「简化」掉 --single-transaction（一致性快照没了，
    但演练仍会绿，因为本机没并发写）；破坏性目标闸被放宽；夹具退化成纯 ASCII
    （字符集那条腿变空断言）；门面行不被电池认（受理面上成盲红）。
    """
    legs = []

    def leg(name, ok, detail=""):
        legs.append((name, ok, detail))

    leg("B1 参数表含 --single-transaction（一致性快照的唯一来源）",
        "--single-transaction" in DUMP_ARGS, " ".join(DUMP_ARGS))
    leg("B1 参数表含 --default-character-set=utf8mb4 与 --add-drop-database",
        "--default-character-set=utf8mb4" in DUMP_ARGS and "--add-drop-database" in DUMP_ARGS)
    leg("B1 对照·参数表里没有 --force（它会跳过错误，把坏 dump 伪装成成功）",
        "--force" not in DUMP_ARGS)

    leg("B2 安全闸：只认这两个一次性端口", SCRATCH_PORTS == {13307, 13308}, str(SCRATCH_PORTS))
    leg("B2 安全闸·反例：开发态 3306 必须被拒绝",
        is_destructive_allowed(3306, SCRATCH_DB, allow_env="") is False, "3306 不在一次性面内")
    leg("B2 安全闸·反例：一次性实例但库名不对也拒绝（防端口撞车时删错库）",
        is_destructive_allowed(13307, "someone_elses_db", allow_env="") is False)
    leg("B2 安全闸·正例：一次性端口 + 一次性库名放行",
        is_destructive_allowed(13307, SCRATCH_DB, allow_env="") is True)
    leg("B2 安全闸·环境变量显式授权才走第二条路",
        is_destructive_allowed(3399, "any_db", allow_env="1") is True)

    fixtures_text = "".join(f[2] for f in FIXTURES) + "".join(str(f[4]) for f in EMOTION_FIXTURES)
    leg("B4 夹具含非 ASCII（否则字符集那条腿是空断言）",
        any(ord(c) > 127 for c in fixtures_text), "%d 字" % len(fixtures_text))
    leg("B4 夹具含反斜杠/制表/换行三种会被转义吃掉的形态",
        any("\\" in f[2] for f in FIXTURES) and any("\t" in f[2] for f in FIXTURES)
        and any("\n" in f[2] for f in FIXTURES))

    try:
        # ⚠️ 必须留住**前后两个** stdout 包装器的引用（模块级名单，不能只留函数局部变量）：
        # `run_all_suites` 顶部会用 `sys.stdout.buffer` 再造一个包装器，而**旧包装器被回收时
        # 会把这块共享 buffer 一起关掉** ⇒ 后续每句 print 都 `ValueError: I/O operation on
        # closed file`。只保住旧的那个不够，两个都要在名单里（同一条坑在 mysql_db_check
        # 里已经踩过并用 _keepalive 解掉，本件照同一做法）。
        _keepalive.append(sys.stdout)
        import run_all_suites as ras
        _keepalive.append(sys.stdout)
        sys.stdout = _keepalive[0]
        re_ok = bool(ras.VERDICT_RE.search(f"{VERDICT}-PASS")) and \
            bool(ras.VERDICT_RE.search(f"{VERDICT}-UNVERIFIED"))
        leg("门面行匹配电池 VERDICT_RE", re_ok, "VERDICT=%s" % VERDICT)
    except Exception as e:
        leg("门面行匹配电池 VERDICT_RE", False, "电池不可导入：%s" % e.__class__.__name__)

    ok = sum(1 for x in legs if x[1])
    for name, passed, detail in legs:
        print("  [%s] %s%s" % ("ok" if passed else "FAIL", name,
                               ("｜" + detail) if detail else ""), flush=True)
    print("%s-SELFTEST-%s %d/%d" % (VERDICT, "PASS" if ok == len(legs) else "FAIL", ok, len(legs)),
          flush=True)
    return 0 if ok == len(legs) else 1


def is_destructive_allowed(port, db, allow_env=None):
    """B2 的闸：只允许打在**本件自己起的一次性实例**上，其余一律拒绝。

    第二条通道（显式授权）存在是为了让「在 CI 上对一次性服务库演练」仍然可表达，
    但它必须由环境变量明确说出，不接受"端口看起来像临时"这种猜测。
    """
    if (allow_env if allow_env is not None else os.environ.get("XINYU_BACKUP_ALLOW_DESTRUCTIVE", "")) == "1":
        return True
    return port in SCRATCH_PORTS and db == SCRATCH_DB


def seed_rows(mysql, port):
    """写入夹具：先清会话，再逐条插。SQL 一律参数化到**语句构造**层面——
    这里只有本件自造的常量夹具，没有外部输入；仍按单引号与反斜杠转义走，
    好让「恢复后逐字节相等」这条断言测的是数据库，不是我的引号处理。
    """
    def esc(s):
        return s.replace("\\", "\\\\").replace("'", "''")
    stmts = ["DELETE FROM chat_message WHERE session_id IN ('s1','s2');",
             "DELETE FROM emotion_record WHERE session_id IN ('s1','s2');"]
    for sid, role, content in FIXTURES:
        stmts.append("INSERT INTO chat_message (session_id, role, content, created_at) "
                     "VALUES ('%s','%s','%s', NOW());" % (sid, role, esc(content)))
    for sid, emo, intensity, secondary, text in EMOTION_FIXTURES:
        sec = "NULL" if secondary is None else "'%s'" % esc(secondary)
        stmts.append("INSERT INTO emotion_record (session_id, emotion, intensity, secondary, text, created_at) "
                     "VALUES ('%s','%s',%s,%s,'%s', NOW());" % (sid, esc(emo), intensity, sec, esc(text)))
    p = subprocess.run(cli_list(mysql, port, SCRATCH_DB, ["-e", " ".join(stmts)]),
                       capture_output=True, timeout=180)
    out = ((p.stdout or b"").decode("utf-8", "replace") + (p.stderr or b"").decode("utf-8", "replace")).strip()
    return p.returncode, out


def _main_tail(dump_bin, fails, mysql_bin, note, port, stamp, target):
    """main 的尾部整段（tail_split 原样搬运，判定/阈值/注释未改一字）。"""
    try:
        print("[backup-drill] %s｜产物 %s" % (note, stamp), flush=True)

        # 建表由**迁移脚本本身**执行：演练要包含「DDL→数据→备份→恢复」整条链，
        # 而不是手工建一套理想表再宣布恢复没问题。
        ddl = (ROOT / "server" / "src" / "main" / "resources" / "db" / "migration"
               / "V1__j4_baseline_schema.sql").read_text(encoding="utf-8")
        p = subprocess.run([str(mysql_bin), "--no-defaults", "-h127.0.0.1", "-P%d" % port,
                            "-uroot", SCRATCH_DB], input=ddl.encode("utf-8"),
                           capture_output=True, timeout=180)
        if p.returncode != 0:
            print("%s-FAIL 建表失败 rc=%s：%s" % (VERDICT, p.returncode,
                  p.stderr.decode("utf-8", "replace")[:300]), flush=True)
            return 1

        rc, out = seed_rows(mysql_bin, port)
        if rc != 0:
            print("%s-FAIL B0 夹具写入失败 rc=%s：%s" % (VERDICT, rc, out[:300]), flush=True)
            return 1

        before_msgs, before_emos = out_counts(mysql_bin, port)
        if (before_msgs, before_emos) != (len(FIXTURES), len(EMOTION_FIXTURES)):
            fails.append("FAIL-B0: 写入后计数应为 %d/%d，实测 %s/%s"
                         % (len(FIXTURES), len(EMOTION_FIXTURES), before_msgs, before_emos))

        # ── B1 备份 ──
        with open(stamp, "wb") as fh:
            p = subprocess.run([str(dump_bin), "--no-defaults", "-h127.0.0.1", "-P%d" % port,
                                "-uroot"] + DUMP_ARGS + [SCRATCH_DB],
                               stdout=fh, stderr=subprocess.PIPE, timeout=300)
        dump_err = (p.stderr or b"").decode("utf-8", "replace").strip()
        if p.returncode != 0:
            fails.append("FAIL-B1: mysqldump rc=%s：%s" % (p.returncode, dump_err[:300]))
        raw = stamp.read_bytes() if stamp.exists() else b""
        if not raw:
            # 「0 命中」先证输入非空：空 dump 会让后面的恢复"成功"而什么都不对账
            fails.append("FAIL-B1: dump 产物为空（%d B）——不是「没有数据」，是备份根本没出来" % len(raw))
        else:
            text = raw.decode("utf-8", "replace")
            for needle in ("chat_message", "emotion_record", "INSERT INTO"):
                if needle not in text:
                    fails.append("FAIL-B1: dump 里没有 %s（产物形状不对）" % needle)
            n_ins = len(re.findall(r"INSERT INTO", text))
            print("[backup-drill] B1 dump=%d B，INSERT 语句块=%d" % (len(raw), n_ins), flush=True)
            if n_ins < 2:
                fails.append("FAIL-B1: dump 里 INSERT 块=%d（两张表都该有数据）" % n_ins)

        if fails:
            return report(fails)

        # ── B2 破坏（DROP 整个库；只允许打在一次性实例上） ──
        # 不复用 q()：它按「查某库」组织参数，而这一条正是让那个库消失
        p = subprocess.run([str(mysql_bin), "--no-defaults", "-h127.0.0.1", "-P%d" % port,
                            "-uroot", "-e", "DROP DATABASE %s;" % SCRATCH_DB],
                           capture_output=True, timeout=180)
        if p.returncode != 0:
            fails.append("FAIL-B2: DROP 失败 rc=%s：%s" % (p.returncode,
                          p.stderr.decode("utf-8", "replace")[:200]))
            return report(fails)
        print("[backup-drill] B2 已 DROP DATABASE %s（一次性实例内）" % SCRATCH_DB, flush=True)

        # ── B3 恢复 ──
        with open(stamp, "rb") as fh:
            p = subprocess.run([str(mysql_bin), "--no-defaults", "-h127.0.0.1", "-P%d" % port, "-uroot"],
                               stdin=fh, capture_output=True, timeout=300)
        if p.returncode != 0:
            fails.append("FAIL-B3: 载回失败 rc=%s：%s" % (p.returncode,
                          p.stderr.decode("utf-8", "replace")[:300]))
            return report(fails)

        # ── B4 对账 ──
        after_msgs, after_emos = out_counts(mysql_bin, port)
        if (after_msgs, after_emos) != (before_msgs, before_emos):
            fails.append("FAIL-B4: 恢复后计数变化 %s/%s → %s/%s"
                         % (before_msgs, before_emos, after_msgs, after_emos))

        # 逐字节比对走 **HEX()** 而不是取文本：`mysql -N -e` 会把结果里的 \n \t \\ 当场转义，
        # 而 Windows 的记录分隔符又是 \r\n —— 夹具本身带真换行，两种「换行」在同一行输出里
        # 无法区分（r169 首跑就是这样把「完全一致的数据」读成不一致）。
        # 让 MySQL 出十六进制、Python 侧按 UTF-8 算同一份十六进制，比较面就只剩字节本身。
        def hex_of(s):
            return s.encode("utf-8").hex().upper()

        rc, got_h = q(mysql_bin, port,
                      "SELECT HEX(CONCAT(role, 0x01, content)) FROM chat_message "
                      "WHERE session_id IN ('s1','s2') ORDER BY id")
        # 0x01 作分隔：它既不在夹具里也不会被 HEX 折叠，比裸接更稳
        want_h = [hex_of("%s\x01%s" % (f[1], f[2])) for f in FIXTURES]
        got_list = [x.strip() for x in got_h.split() if x.strip()]
        if got_list != want_h:
            fails.append("FAIL-B4: 消息内容不是逐字节相等（HEX 对账）\n  发=%s\n  收=%s"
                         % (want_h, got_list))

        rc, got_e = q(mysql_bin, port,
                     "SELECT HEX(CONCAT(emotion, 0x01, IFNULL(secondary, 0x00), 0x01, text)) "
                     "FROM emotion_record WHERE session_id IN ('s1','s2') ORDER BY id")
        want_e = [hex_of("%s\x01%s\x01%s" % (f[1], f[3] if f[3] is not None else "\x00", f[4]))
                  for f in EMOTION_FIXTURES]
        got_e_list = [x.strip() for x in got_e.split() if x.strip()]
        if got_e_list != want_e:
            fails.append("FAIL-B4: 情绪记录不是逐字节相等（HEX 对账）\n  发=%s\n  收=%s"
                         % (want_e, got_e_list))

        rc, idx = q(mysql_bin, port,
                    "SELECT COUNT(DISTINCT INDEX_NAME) FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA=DATABASE() AND INDEX_NAME<>'PRIMARY'")
        if idx.strip() != "2":
            fails.append("FAIL-B4: 恢复后非主键索引数应为 2，实测 %r（索引没了=表回来了但查询面废了）" % idx)
        rc, coll = q(mysql_bin, port,
                     "SELECT TABLE_NAME, TABLE_COLLATION FROM information_schema.TABLES "
                     "WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME")
        if "utf8mb4" not in coll:
            fails.append("FAIL-B4: 恢复后表 collation 不是 utf8mb4：%s" % coll)
        return report(fails)
    finally:
        if target is not None:
            target.teardown()

def main():
    if "--selftest" in sys.argv[1:]:
        return selftest()

    try:
        # 同 selftest 里的坑：mysql_db_check 顶部也会换 sys.stdout，被替换掉的那个包装器
        # 一旦被回收就会关掉共享 buffer ⇒ 本件后续 print 全部报 closed file。两个引用都上名单。
        _keepalive.append(sys.stdout)
        import mysql_db_check as m
        _keepalive.append(sys.stdout)
        sys.stdout = _keepalive[0]
    except Exception as e:
        print("%s-UNVERIFIED 未验：无法复用 mysql_db_check 的取库通道（%s: %s）"
              % (VERDICT, e.__class__.__name__, e), flush=True)
        return 2

    dump_bin, mysql_bin = m.local_bin("mysqldump"), m.local_bin("mysql")
    if not (dump_bin and mysql_bin):
        print("%s-UNVERIFIED 未验：本机缺 mysqldump.exe 或 mysql.exe（basedir=%s，可设 XINYU_MYSQL_BASEDIR）"
              % (VERDICT, m.LOCAL_BASEDIR), flush=True)
        return 2

    # 取库：只走一次性实例。环境变量目标必须带显式授权，否则宁可判未验。
    env_jdbc = os.environ.get("XINYU_BACKUP_MYSQL_PORT", "").strip()
    if env_jdbc:
        port = int(env_jdbc)
        if not is_destructive_allowed(port, SCRATCH_DB):
            print("%s-UNVERIFIED 未验：目标端口 %s 不是本件的一次性实例，且未设 "
                  "XINYU_BACKUP_ALLOW_DESTRUCTIVE=1 ⇒ 拒绝在其上 DROP DATABASE" % (VERDICT, port), flush=True)
            return 2
        target, note = None, "取库=显式指定端口 %s（已授权破坏性演练）" % port
    else:
        target, err = m.start_local("utf8mb4")
        if target is None:
            print("%s-UNVERIFIED 未验：一次性实例起不来（%s）" % (VERDICT, err), flush=True)
            return 2
        port = m.LOCAL_PORTS["utf8mb4"]
        note = "取库=本机 mysqld 一次性实例（端口 %s，库 %s）" % (port, SCRATCH_DB)

    stamp = DUMP_DIR / ("xinyu-backup-%d.sql" % port)
    fails = []
    return _main_tail(dump_bin, fails, mysql_bin, note, port, stamp, target)


def out_counts(mysql_bin, port):
    """两条计数各出一值，取不到就带上 rc 标记（不许把「查询失败」折成 0）。

    ⚠️ 这里**必须返回 int**：客户端输出是文本，而调用点比的是 `len(FIXTURES)` 这种整数，
    `"3" != 3` 会造出一条「实测 3/2 应为 3/2」的自相矛盾红（r169 首跑真踩到了）。
    """
    out = []
    for sql in ("SELECT COUNT(*) FROM chat_message WHERE session_id IN ('s1','s2')",
                "SELECT COUNT(*) FROM emotion_record WHERE session_id IN ('s1','s2')"):
        rc, got = q(mysql_bin, port, sql)
        text = got.strip()
        try:
            out.append(int(text.splitlines()[-1].strip()))
        except (ValueError, IndexError):
            out.append("rc%s:%s" % (rc, text.replace("\n", " ")[:80]))
    return out[0], out[1]


def report(fails):
    if fails:
        for line in fails:
            print(line, flush=True)
        print("%s-FAIL 共 %d 处" % (VERDICT, len(fails)), flush=True)
        return 1
    print("%s-PASS 四条腿全过（备份/删库/载回/逐字节对账）" % VERDICT, flush=True)
    return 0


if __name__ == "__main__":
    # r173 兜底：未捕获异常必须留下具名结论行，否则电池只见 rc≠0（BLIND-RED）
    from check_instrument import install_excepthook
    install_excepthook("MYSQL-BACKUP")
    sys.exit(main())
