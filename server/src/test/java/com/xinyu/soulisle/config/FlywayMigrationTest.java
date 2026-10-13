package com.xinyu.soulisle.config;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 版本化迁移的行为回执（r169）。
 *
 * <p>为什么必须有这一类：修前 DDL 只由 {@code spring.sql.init.mode=always} 跑
 * {@code CREATE TABLE IF NOT EXISTS}。那种形态**只能建表、不能改表** —— 加一列、换一个
 * COLLATE，对已经存在的库永远不生效，而且**没有任何地方记录「这个库跑到第几版了」**。
 * 于是「数据迁移与一致性」这条要求根本没有可验收的对象。本类把迁移变成可复算的产物。
 *
 * <p>库一律用 {@code jdbc:h2:mem}：06-constraints 的 env_mode 红线禁止测试写演示库
 * {@code server/data/xinyu.mv.db}，而内存库每个用例都是全新实例，跨重启腿才有意义。
 */
class FlywayMigrationTest {

    private static final AtomicInteger SEQ = new AtomicInteger();

    /** 每次一个新名字的内存库：同名的两个用例会在同一个库里串状态（内存库按名共享）。 */
    private static String freshUrl() {
        return "jdbc:h2:mem:xinyu-flyway-" + SEQ.incrementAndGet()
                + ";MODE=MySQL;DB_CLOSE_DELAY=-1;DB_CLOSE_ON_EXIT=FALSE";
    }

    private static org.flywaydb.core.Flyway flyway(String url) {
        return org.flywaydb.core.Flyway.configure()
                .dataSource(url, "sa", "")
                .locations("classpath:db/migration")
                .table("flyway_schema_history")
                .baselineOnMigrate(true)
                .baselineVersion("0")
                .validateOnMigrate(true)
                .cleanDisabled(true)
                .load();
    }

    private static boolean tableExists(Connection c, String table) throws Exception {
        try (ResultSet rs = c.getMetaData().getTables(c.getCatalog(), null, "%", new String[]{"TABLE"})) {
            while (rs.next()) {
                if (table.equalsIgnoreCase(rs.getString(3))) {
                    return true;
                }
            }
        }
        return false;
    }

    @Test
    @DisplayName("空库首跑：执行 1 个迁移，两张表落地，历史表记下版本 1")
    void migrateFromEmpty() throws Exception {
        String url = freshUrl();
        var results = flyway(url).migrate();
        assertEquals(1, results.migrationsExecuted, "空库应当恰好前滚 1 个版本");
        try (Connection c = DriverManager.getConnection(url, "sa", "")) {
            assertTrue(tableExists(c, "chat_message"));
            assertTrue(tableExists(c, "emotion_record"));
            // 表名与列名都**必须加引号**：Flyway 在 H2 上把历史表建成的就是小写
            // （flyway_schema_history / version / success），而 H2 对**未加引号**的标识符按
            // 大写折叠 ⇒ 裸写 version 会被读成 VERSION 而报「Column "VERSION" not found」。
            // 这条不是测试的怪癖，是「同一份 DDL 在 H2 与 MySQL 上标识符大小写规则不同」的现场。
            try (Statement st = c.createStatement();
                 ResultSet rs = st.executeQuery(
                         "SELECT COUNT(*) FROM \"flyway_schema_history\" WHERE \"version\" = '1' AND \"success\" = TRUE")) {
                rs.next();
                assertEquals(1, rs.getInt(1), "历史表须记下**成功**的版本 1（success 位没落=下次启动重跑）");
            }
        }
    }

    @Test
    @DisplayName("二次启动幂等：前滚 0 个版本；这是「重启不重复建表也不报错」的那条腿")
    void secondRunIsNoOp() {
        String url = freshUrl();
        flyway(url).migrate();
        assertEquals(0, flyway(url).migrate().migrationsExecuted);
    }

    @Test
    @DisplayName("存量库接入：表已存在但没有历史表 ⇒ 基线化后前滚，不得抛「非空库无历史」")
    void takesOverExistingSchema() throws Exception {
        String url = freshUrl();
        // 手工造出「Flyway 之前」的世界：只有两张业务表，没有 flyway_schema_history
        try (Connection c = DriverManager.getConnection(url, "sa", "");
             Statement st = c.createStatement()) {
            st.execute("CREATE TABLE chat_message (id BIGINT AUTO_INCREMENT PRIMARY KEY, s VARCHAR(64))");
            st.execute("CREATE TABLE emotion_record (id BIGINT AUTO_INCREMENT PRIMARY KEY, s VARCHAR(64))");
        }
        var results = flyway(url).migrate();
        try (Connection c = DriverManager.getConnection(url, "sa", "")) {
            assertTrue(tableExists(c, "flyway_schema_history"), "基线化必须建出历史表");
            // V1 在存量库上照跑（baseline-version=0），靠脚本自身的 IF NOT EXISTS 保持幂等；
            // 若哪天 baseline-version 被改回默认的 1，V1 会被静默跳过 ⇒ 这里当场红。
            assertEquals(1, results.migrationsExecuted,
                    "存量库上 V1 仍应执行一次；被跳过说明 baseline-version 被改回 1");
            try (Statement st = c.createStatement();
                 ResultSet rs = st.executeQuery(
                         "SELECT COUNT(*) FROM \"flyway_schema_history\" WHERE \"type\" = 'BASELINE'")) {
                rs.next();
                assertEquals(1, rs.getInt(1), "基线行是「这个库来自 Flyway 之前」的唯一留痕");
            }
        }
    }

    @Test
    @DisplayName("clean 被硬闸关掉：演示机上 flyway.clean 会整库 DROP，不许是一个能误触的方法")
    void cleanIsDisabled() {
        String url = freshUrl();
        org.flywaydb.core.Flyway fw = flyway(url);
        fw.migrate();
        // 行为断言（不碰 Configuration 的 getter）：真关掉时 clean() 必抛且点名 clean；
        // 若哪天 clean-disabled 被改回 false，这里会立刻红——而不是让「整库被清空」变成一个可调用的方法。
        var ex = org.junit.jupiter.api.Assertions.assertThrows(
                org.flywaydb.core.api.FlywayException.class, fw::clean);
        assertTrue(ex.getMessage().toLowerCase().contains("clean"),
                "红因要点名 clean 被禁，而不是一个笼统的失败：" + ex.getMessage());
    }

    @Test
    @DisplayName("DDL 结构守卫：两张 CREATE TABLE 各自自带 ENGINE/utf8mb4/COLLATE，且无游离 CREATE INDEX")
    void migrationDeclaresCharsetInline() throws Exception {
        String sql = readV1();
        int tables = count(sql, "CREATE TABLE IF NOT EXISTS");
        int engines = count(sql, "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        assertEquals(tables, engines,
                "每张建表都必须自带存储引擎与字符集声明（少一张=那张跟随服务器默认字符集）");
        assertEquals(2, tables, "J4 基线就是两张表；多出来的建表要重新核对字符集守卫");
        // 索引必须内联：MySQL 不支持 CREATE INDEX IF NOT EXISTS（实测 ERROR 1064），
        // 而裸 CREATE INDEX 第二次启动两侧都报错 ⇒ 游离的一条 CREATE INDEX 就是回归。
        // 判「语句」而非判「全文」：本文件头注释里就正引用着 CREATE INDEX 这个词，
        // 按全文扫会把**说明**读成**违规**（同一形状在 r130 那轮反例腿里踩过一次）。
        String statements = sql.replaceAll("(?m)^\\s*--.*$", "");
        assertFalse(statements.matches("(?is).*\\bCREATE\\s+INDEX\\b.*"),
                "出现游离 CREATE INDEX —— 幂等性由表级 IF NOT EXISTS 承载，索引必须内联");
        assertTrue(statements.toLowerCase().contains("utf8mb4"), "剥掉注释后仍须含字符集声明");
        assertFalse(statements.toLowerCase().contains("drop table"),
                "迁移脚本里不得有 DROP（不可逆动作要走备份演练那条通道，不在前滚脚本里）");
    }

    /** V1 文件名是契约的一部分：改名=历史表里的 description 与实际脚本脱节，故在此锁死。 */
    private static String readV1() throws Exception {
        ClassPathResource res = new ClassPathResource("db/migration/V1__j4_baseline_schema.sql");
        assertTrue(res.exists(), "db/migration/V1__j4_baseline_schema.sql 必须在 classpath 上");
        try (InputStream in = res.getInputStream()) {
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    private static int count(String haystack, String needle) {
        int n = 0;
        int i = haystack.indexOf(needle);
        while (i >= 0) {
            n++;
            i = haystack.indexOf(needle, i + needle.length());
        }
        return n;
    }
}
