# -*- coding: utf-8 -*-
"""服务端硬化常驻棘轮（r128 新增）：成本面 / 内存面 / 记忆面三道新能力不许悄悄退化

为什么做这条判据（**不是**"新功能需要测试"这种泛理由）：
本仓最贵的一类事故形态是「**改了没尺**」——r127 §8 的 S5/S8/S9/S10/S11 全是同一族：
先有了能力主张，几轮之后才发现没有常驻尺，于是"降回去了"没人拦。本轮三项改造
（限流闸 / 访问日志 / BM25 长期记忆）如果只有 JUnit 保护，JUNIT 会被后人整体删掉或
改宽松，而仓库层面看不出任何异常。

所以这里做的是**仓库面的结构断言**，与 JUnit 正交：
  JUnit 答"行为对不对"，本脚本答"**这套能力还在不在**"。

四条断言（每条都必须有反例腿，见 --selftest）：
  H1 限流闸在位：ApiGuardFilter 类存在 + 429/rate-limited 语义在源码里 + 有 Retry-After
  H2 体上限在位：max-body-bytes 配置项在 application.yml 且默认值 > 0
  H3 访问日志在位：AccessLogFilter 在位，且**不记请求体/密钥**（密钥零落盘红线）
  H4 长期记忆检索在位：MemorySearchService + /api/memory/search 三处同时在
     （控制器路由、openapi 声明、docs/API.md 人读手册）—— 少一处就是文档漂移

⚠️ 自检纪律（照本仓 r127 §8 的教训）：
  - 判据不许读**没量到的东西**当零：每个断言先证「输入面非空」，输入为空 ⇒ rc=2 环境未验
  - 不许有恒真腿：--selftest 注入变异必须把每条断言**单独**打翻，否则这条腿是装饰

退出码：0=SERVER-HARDENING-PASS 1=任一断言红 2=环境未验（源码面缺失，不得声称已验）
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
JAVA_SRC = ROOT / "server" / "src" / "main" / "java" / "com" / "xinyu" / "soulisle"
YML = ROOT / "server" / "src" / "main" / "resources" / "application.yml"
SPEC = ROOT / "docs" / "openapi.yaml"
MANUAL = ROOT / "docs" / "API.md"

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  -> {detail}" if detail else ""))


def java_file(rel):
    """按相对路径读 Java 源；不存在返回 None（由调用方区分「缺失」与「无该词」）。"""
    p = JAVA_SRC / rel
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8", errors="replace")


def strip_comments(src):
    """去掉 // 行注释与 /* */ 块注释。

    为什么必须去：H3 要扫全文找密钥字面量，而本仓的 javadoc 里**正当地写着**
    「绝不记请求体、响应体、Authorization 头与任何密钥」—— 散文里出现被禁词，
    恰恰说明这条红线被写清楚了。拿注释当代码判红，就是把说明文档判成缺陷
    （第二版 H3 就是这么假红的）。
    """
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"//[^\n]*", " ", src)


def h1_rate_limit_present():
    src = java_file(Path("config") / "ApiGuardFilter.java")
    if src is None:
        return False, "ApiGuardFilter.java 不在磁盘上"
    need = {
        "429": "429",
        "rate-limited 错误体": "rate-limited",
        "Retry-After 响应头": "Retry-After",
        "令牌桶类": "class Bucket",
    }
    miss = [k for k, v in need.items() if v not in src]
    return (not miss), ("" if not miss else f"缺：{miss}")


def h2_body_cap_present():
    if not YML.exists():
        return False, "application.yml 不在磁盘上"
    text = YML.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"max-body-bytes:\s*\$\{[^:]+:(\d+)\}", text)
    if not m:
        return False, "application.yml 里找不到带默认值的 max-body-bytes"
    default = int(m.group(1))
    if default <= 0:
        return False, f"max-body-bytes 默认值 = {default}，配 0 等于关掉这道闸"
    return True, f"max-body-bytes 默认 {default} B"


def h3_access_log_present():
    src = java_file(Path("config") / "AccessLogFilter.java")
    if src is None:
        return False, "AccessLogFilter.java 不在磁盘上"
    if "access" not in src:
        return False, "没有 access 日志输出"
    # 红线：整个文件里不得出现「把载荷或密钥读出来」的写法。
    # ⚠️ 第一版只扫含 LOGGER. 的行 —— 但载荷是先拼进 line 变量、再交给 logger 的，
    # 拼接那行并不含 LOGGER.，于是注入了 getContentAsString 照样判绿（装饰腿）。
    # 正解：在一个专职日志过滤器里，任何 getContentAsString/Authorization/密钥字段
    # 的出现本身就是可疑的，不必要求它与 LOGGER. 同行。
    bad = []
    code_only = strip_comments(src).lower()
    for token in ("getcontentasstring", "authorization", "apikey",
                  "this.key", "llm.key", "xinyu-token"):
        if token in code_only:
            bad.append(token)
    return (not bad), ("" if not bad else f"疑似把载荷/密钥送进日志：{bad}")


def h4_memory_search_present():
    svc = java_file(Path("service") / "MemorySearchService.java")
    ctl = java_file(Path("api") / "MemoryController.java")
    if svc is None:
        return False, "MemorySearchService.java 不在磁盘上"
    if ctl is None or "/api/memory/search" not in ctl:
        return False, "MemoryController 里没有 /api/memory/search 路由"
    if not SPEC.exists():
        return False, "docs/openapi.yaml 不在磁盘上"
    if "/api/memory/search" not in SPEC.read_text(encoding="utf-8", errors="replace"):
        return False, "openapi.yaml 没有声明 /api/memory/search"
    if not MANUAL.exists():
        return False, "docs/API.md 不在磁盘上"
    if "/api/memory/search" not in MANUAL.read_text(encoding="utf-8", errors="replace"):
        return False, "docs/API.md 人读手册没有这条接口"
    return True, "控制器 + openapi + 人读手册 三处齐备"


def h5_daily_quota_present():
    """r130：成本**总量**闸（瞬时令牌桶挡不住「每分钟 1 次、一天 1440 次」的慢速白嫖）。"""
    ledger = java_file(Path("config") / "UsageLedger.java")
    filt = java_file(Path("config") / "QuotaFilter.java")
    ctl = java_file(Path("api") / "UsageController.java")
    if ledger is None:
        return False, "UsageLedger.java 不在磁盘上"
    if filt is None or "daily-quota-exceeded" not in filt:
        return False, "QuotaFilter 里没有日额熔断的错误体语义"
    if ctl is None or "/api/usage" not in ctl:
        return False, "UsageController 里没有 /api/usage 路由"
    yml = YML.read_text(encoding="utf-8", errors="replace") if YML.exists() else ""
    if "daily-requests" not in yml:
        return False, "application.yml 没有 daily-requests 配置位（闸没有开关等于不可运营）"
    for doc, need in ((SPEC, "/api/usage"), (MANUAL, "/api/usage")):
        if not doc.exists():
            return False, f"{doc.name} 不在磁盘上"
        if need not in doc.read_text(encoding="utf-8", errors="replace"):
            return False, f"{doc.name} 没有声明 /api/usage"
    return True, "台账 + 过滤器 + 读数端点 + 配置位 + openapi + 人读手册 六处齐备"


def h6_memory_port_present():
    """r130：记忆可携带（导出/导入）。`skipped` 是幂等的判别串，不是可省略的计数。"""
    svc = java_file(Path("service") / "MemoryPortService.java")
    ctl = java_file(Path("api") / "MemoryPortController.java")
    if svc is None:
        return False, "MemoryPortService.java 不在磁盘上"
    if "skipped" not in svc:
        return False, "导入实现里没有 skipped 计数 ⇒ 幂等这条性质没有可判的把手"
    if ctl is None or "/api/memory/export" not in ctl or "/api/memory/import" not in ctl:
        return False, "控制器里缺 export/import 两条路由"
    for doc, need in ((SPEC, "/api/memory/export"), (MANUAL, "/api/memory/export"),
                      (SPEC, "/api/memory/import"), (MANUAL, "/api/memory/import")):
        if not doc.exists():
            return False, f"{doc.name} 不在磁盘上"
        if need not in doc.read_text(encoding="utf-8", errors="replace"):
            return False, f"{doc.name} 没有声明 {need}"
    return True, "服务 + 控制器 + openapi + 人读手册 四处齐备（含幂等计数把首）"


MIGRATION = ROOT / "server" / "src" / "main" / "resources" / "db" / "migration" / "V1__j4_baseline_schema.sql"
DDL_CHARSET_CLAUSE = "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
# 借连接预算的上限：库不可达时用户被挂住的最长时间。默认值是 HikariCP 的 30s，
# 而 30s 挂起 ≠ 快速回落，所以这条断言判的是「有没有被主动收紧」，不是「有没有这一行」。
POOL_BUDGET_MAX_MS = 10000


def h7_mysql_face_present():
    """r169：MySQL 目标库面的四件结构（字符集自带 / 池预算收紧 / 降级归因 / 迁移通道）。

    立因：这四项在 2026-10-13 之前**逐项都是缺的**，而每一项的缺失都不会让任何既有判据变红——
    `application.yml` 从 J4 起就写着「生产切 MySQL」，`_test/` 全库 grep `mysql` 却零命中过，
    这正是「配置口子存在 ≠ 能力成立」。本条把这些能力钉成仓库面结构断言，删一项就红。
    """
    bad = []
    if not MIGRATION.exists():
        return False, "迁移脚本不在位（db/migration/V1__j4_baseline_schema.sql）⇒ DDL 无处安放"
    ddl = MIGRATION.read_text(encoding="utf-8", errors="replace")
    tables = len(re.findall(r"CREATE TABLE IF NOT EXISTS", ddl))
    clauses = ddl.count(DDL_CHARSET_CLAUSE)
    if tables == 0:
        bad.append("迁移脚本里零张 CREATE TABLE（取数面为空，不得读成通过）")
    elif clauses != tables:
        bad.append(f"建表 {tables} 张但自带字符集声明只有 {clauses} 处 ⇒ 少的那张会跟随服务器默认字符集")
    yml = YML_TEXT()
    if "flyway:" not in yml:
        bad.append("application.yml 没有 spring.flyway 段 ⇒ DDL 执行通道不明（迁移脚本无人认领）")
    if "hikari:" not in yml:
        bad.append("application.yml 无 spring.datasource.hikari 子树 ⇒ 池参数全吃默认（借不到连接等 30s）")
    m = re.search(r"connection-timeout:\s*\$\{[^:}]+:(\d+)\}", yml)
    if not m:
        bad.append("连接池 connection-timeout 未显式配置（判据要的是「被收紧过」这一事实）")
    elif int(m.group(1)) > POOL_BUDGET_MAX_MS:
        bad.append("connection-timeout=%sms > %sms ⇒ 库挂掉时请求仍被长时间挂住，不是快速回落"
                   % (m.group(1), POOL_BUDGET_MAX_MS))

    advice = java_file(Path("config") / "DatabaseFailureAdvice.java")
    failure = java_file(Path("config") / "DbFailure.java")
    if failure is None or "@ExceptionHandler(DataAccessException.class)" not in (advice or ""):
        bad.append("缺 DbFailure/DatabaseFailureAdvice ⇒ 库故障仍以 Spring 白标 500 出去")
    else:
        kinds = len(re.findall(r"^\s{4}[A-Z_]+\(\"db-", failure, re.M))
        if kinds < 6:
            bad.append(f"归因类只有 {kinds} 种（六类各对应一种客户端处置，合并即失去区分力）")

    health = java_file(Path("api") / "DatabaseHealthController.java")
    if health is None or '"/api/health/db"' not in health:
        bad.append("健康面没有独立的 DB 那一面 ⇒ 库全挂时 /api/health 仍报 UP")
    svc = java_file(Path("service") / "MemoryService.java")
    if svc is None or "@Transactional" not in svc:
        bad.append("MemoryService 无事务边界 ⇒ 「清除我的数据」可能只删掉一半（隐私债形态）")
    if (ROOT / "server" / "pom.xml").read_text(encoding="utf-8", errors="replace").count("flyway-core") < 1:
        bad.append("pom 里没有 flyway-core ⇒ 版本化迁移通道没了，DDL 回到只能建表不能改表")
    return (not bad), "；".join(bad) or "四件齐备（字符集自带×2 / 池预算≤%dms / 六类归因+Advice / Flyway+事务+DB 健康面）" % POOL_BUDGET_MAX_MS


def YML_TEXT():
    return YML.read_text(encoding="utf-8", errors="replace") if YML.exists() else ""


CHECKS = [
    ("H1 限流闸在位（429 + Retry-After + 令牌桶）", h1_rate_limit_present),
    ("H2 请求体上限在位且默认值非零", h2_body_cap_present),
    ("H3 结构化访问日志在位且不记载荷/密钥", h3_access_log_present),
    ("H4 BM25 长期记忆检索三处齐备", h4_memory_search_present),
    ("H5 按日用量闸与读数端点齐备（成本总量面）", h5_daily_quota_present),
    ("H6 记忆导出/导入齐备且幂等计数在首（数据可携带）", h6_memory_port_present),
    ("H7 MySQL 面四件结构（字符集/池预算/降级归因/迁移通道）", h7_mysql_face_present),
]


def run_checks():
    for name, fn in CHECKS:
        ok, detail = fn()
        check(name, ok, detail)
    return results


def selftest():
    """变异腿：每条断言单独打翻一次，证明它有牙。

    ⚠️ 第一版三条腿全是**空操作**（变异串写错 ⇒ replace/re.sub 什么也没替 ⇒ 断言照绿），
    判据却报「恒真」。教训与本仓 r127 §8 同族：**变异腿必须先断言"变异真的落盘了"**，
    否则测的是「变异前的原样」。这里统一走 `mutate()`，它在替换未命中时直接炸。
    """
    bad = []
    guard_path = JAVA_SRC / "config" / "ApiGuardFilter.java"
    guard = guard_path.read_bytes() if guard_path.exists() else None
    # 备份一律按**字节**取、按字节还：文本模式的读写在 Windows 上会翻译行尾，
    # 于是一次「什么都没改的还原」也能把工作树写脏（r169 实测：迁移脚本报 M）。
    # 本仓另有 EOL 平价判据，行尾被顺手改掉会连带别的腿一起红 —— 变异腿的宿主必须逐字节回原样。
    yml_backup = YML.read_bytes() if YML.exists() else None
    log_path = JAVA_SRC / "config" / "AccessLogFilter.java"
    log_backup = log_path.read_bytes() if log_path.exists() else None
    manual_backup = MANUAL.read_bytes() if MANUAL.exists() else None
    mig_backup = MIGRATION.read_bytes() if MIGRATION.exists() else None

    def mutate(path, old, new):
        """替换并**当场验证**命中；未命中就抛 —— 空操作变异腿不许静默通过。"""
        text = path.read_bytes().decode("utf-8")
        if old not in text:
            raise AssertionError(f"变异腿空操作：{path.name} 里找不到 {old!r}")
        path.write_bytes(text.replace(old, new, 1).encode("utf-8"))

    try:
        # H1：抹掉「被限流时返回的那个错误体」语义，必须翻红。
        # ⚠️ 不能拿 429 当变异锚点：它在 javadoc 里也出现，count=1 只替掉注释那处，
        # 真正的业务那处原封不动 ⇒ 断言照绿（第一版就是这么白跑的）。
        # 锚点必须选**只出现一次**的判别串。
        mutate(guard_path, "rate-limited", "teapot")
        if h1_rate_limit_present()[0]:
            bad.append("H1 变异腿：抹掉限流错误体后仍判绿 ⇒ H1 恒真")

        # H2：把默认值改成 0（等于关掉这道闸），必须翻红。
        # ⚠️ yml 里是 `max-body-bytes: ${...}`，冒号后有空格，正则里必须留 \s*。
        yml_text = YML.read_bytes().decode("utf-8")
        pat = re.compile(r"(max-body-bytes:\s*\$\{[^:}]+:)\s*\d+")
        if not pat.search(yml_text):
            raise AssertionError("变异腿空操作：yml 里匹配不到 max-body-bytes 默认值")
        YML.write_bytes(pat.sub(r"\g<1>0", yml_text, count=1).encode("utf-8"))
        if h2_body_cap_present()[0]:
            bad.append("H2 变异腿：默认值改 0 后仍判绿 ⇒ H2 恒真")

        # H3：往日志行里塞请求体，必须翻红
        mutate(JAVA_SRC / "config" / "AccessLogFilter.java",
               '",\\"ms\\":" + millis',
               '",\\"body\\":\\"" + request.getContentAsString() + "\\",\\"ms\\":" + millis')
        if h3_access_log_present()[0]:
            bad.append("H3 变异腿：日志塞入请求体后仍判绿 ⇒ H3 恒真")

        # H4：从人读手册里删掉这条接口，必须翻红
        mutate(MANUAL, "/api/memory/search", "/api/removed")
        if h4_memory_search_present()[0]:
            bad.append("H4 变异腿：手册删掉接口后仍判绿 ⇒ H4 恒真")

        # H5/H6：把人读手册里的端点改名，必须翻红。
        # ⚠️ 这里**必须全量替换**而不是 mutate() 的单次替换：`/api/usage` 在 API.md 里
        # 出现在章节标题与 curl 示例两处，只替一处 ⇒ 另一处仍在 ⇒ 断言照绿（同 r128 的
        # 「锚点必须只出现一次」，但那次的正解是换锚点，这次的正解是全替换——因为任何一处
        # 存活都构成「文档没删干净」，我们要的就是这个语义）。
        for anchor, repl, fn, label in (
                ("/api/usage", "/api/removed-usage", h5_daily_quota_present, "H5"),
                ("/api/memory/export", "/api/removed-export", h6_memory_port_present, "H6")):
            text = MANUAL.read_bytes().decode("utf-8")
            if anchor not in text:
                raise AssertionError(f"变异腿空操作：手册里找不到 {anchor}")
            MANUAL.write_bytes(text.replace(anchor, repl).encode("utf-8"))
            if fn()[0]:
                bad.append(f"{label} 变异腿：手册改名 {anchor} 后仍判绿 ⇒ {label} 恒真")
        # H7 变异 A：把**其中一张**表的字符集声明改成 latin1。
        # 判据问的是「每张建表都自带 charset」，所以只改一处也必须翻红——改成两处才红
        # 就等于这条腿只防「整体删除」，不防「新加一张表忘了带」。
        mutate(MIGRATION, DDL_CHARSET_CLAUSE,
               "ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci")
        if h7_mysql_face_present()[0]:
            bad.append("H7 变异腿：一张表回落 latin1 后仍判绿 ⇒ 字符集那条腿恒真")

        # H7 变异 B：把借连接预算改回 HikariCP 默认的 30s，必须翻红。
        # 这条腿锁的不是「有没有这一行」，而是「有没有被主动收紧过」——
        # 把 5000 改回 30000 在文本上仍然"配置存在"，但快速回落这件事已经没了。
        mutate(YML, "${XINYU_DB_CONNECTION_TIMEOUT_MS:5000}",
               "${XINYU_DB_CONNECTION_TIMEOUT_MS:30000}")
        if h7_mysql_face_present()[0]:
            bad.append("H7 变异腿：池预算改回 30s 后仍判绿 ⇒ 连接配置那条腿恒真")
    except AssertionError as e:
        bad.append(str(e))
    finally:
        # 还原必须放在 finally：任一腿崩了也不能把源码/文档留在变异态。
        # ⚠️ 第一版漏还原 MANUAL，直接把 docs/API.md 的接口名写成 /api/removed。
        if yml_backup is not None:
            YML.write_bytes(yml_backup)
        if log_backup is not None:
            log_path.write_bytes(log_backup)
        if guard is not None:
            guard_path.write_bytes(guard)
        if manual_backup is not None:
            MANUAL.write_bytes(manual_backup)
        if mig_backup is not None:
            MIGRATION.write_bytes(mig_backup)

    # 还原后再跑一遍原样：必须全绿，否则上面的"绿"是变异残留
    still_ok = [n for n, fn in CHECKS if not fn()[0]]
    if still_ok:
        bad.append(f"还原后仍判红（变异没被完全撤销）：{still_ok}")

    print("SELFTEST-PASS: H1–H7 各条变异腿均把对应断言单独打翻、还原后原样零红"
          if not bad else "SELFTEST-FAIL: " + "; ".join(bad))
    return 1 if bad else 0


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())

    if not JAVA_SRC.is_dir():
        print("SERVER-HARDENING-ENV-UNVERIFIED: 服务端源码面不在预期位置，不得声称已验")
        return 2

    run_checks()
    red = [n for n, ok, _ in results if not ok]
    total = len(results)
    if red:
        print(f"合计 {total} 项，红 {len(red)}")
        for n in red:
            print(f"  🔴 {n}")
        print("SERVER-HARDENING-FAIL")
        return 1
    print(f"合计 {total} 项，红 0")
    print("SERVER-HARDENING-PASS 限流闸/体上限/访问日志/BM25 检索/按日用量闸/记忆导出导入/"
          "MySQL 面结构 七道能力均仍在位")
    return 0


if __name__ == "__main__":
    sys.exit(main())