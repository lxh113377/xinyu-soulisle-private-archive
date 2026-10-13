package com.xinyu.soulisle.api;

import com.zaxxer.hikari.HikariDataSource;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.flywaydb.core.Flyway;

import javax.sql.DataSource;
import java.io.PrintWriter;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * 数据库面自证（r169）。
 *
 * <p>这条面要锁的是「库死了要看得出来」。修前 {@code /api/health} 只看 index.html 与 vendor
 * 目录，库完全连不上时它仍回 {@code status=UP} ⇒ 客户端与判据都拿不到「该回落本地存储」的输入。
 *
 * <p>三个分支各一条：UP（真 H2 + Flyway 后的库）/ DOWN（取连接必抛）/ 非 Hikari 实现
 * （池指标只能报 unverified，不能猜一套数字）。
 */
class DatabaseHealthControllerTest {

    private static final AtomicInteger SEQ = new AtomicInteger();

    private static String freshUrl() {
        return "jdbc:h2:mem:xinyu-dbhealth-" + SEQ.incrementAndGet() + ";MODE=MySQL;DB_CLOSE_DELAY=-1";
    }

    /** 取连接必抛的 DataSource：模拟库挂了。其余 DataSource 方法一律如实未支持，不静默返回 null。 */
    private static DataSource broken() {
        return new DataSource() {
            @Override
            public Connection getConnection() {
                throw new IllegalStateException("connection refused");
            }

            @Override
            public Connection getConnection(String u, String p) {
                return getConnection();
            }

            @Override
            public PrintWriter getLogWriter() {
                throw new UnsupportedOperationException();
            }

            @Override
            public void setLogWriter(PrintWriter out) {
                throw new UnsupportedOperationException();
            }

            @Override
            public void setLoginTimeout(int seconds) {
                throw new UnsupportedOperationException();
            }

            @Override
            public int getLoginTimeout() {
                return 0;
            }

            @Override
            public java.util.logging.Logger getParentLogger() {
                throw new UnsupportedOperationException();
            }

            @Override
            public <T> T unwrap(Class<T> iface) {
                throw new UnsupportedOperationException();
            }

            @Override
            public boolean isWrapperFor(Class<?> iface) {
                return false;
            }
        };
    }

    private static HikariDataSource hikari(String url) {
        HikariDataSource ds = new HikariDataSource();
        ds.setJdbcUrl(url);
        ds.setUsername("sa");
        ds.setPassword("");
        ds.setPoolName("TestPool");
        ds.setMaximumPoolSize(4);
        ds.setMinimumIdle(1);
        ds.setConnectionTimeout(5000);
        return ds;
    }

    @Test
    @DisplayName("UP 侧：Hikari + 已迁移的 H2 ⇒ status=UP、两张表齐、池水位是实测数字")
    void upReportsTablesAndPool() {
        String url = freshUrl();
        Flyway.configure().dataSource(url, "sa", "").locations("classpath:db/migration")
                .baselineOnMigrate(true).baselineVersion("0").load().migrate();
        HikariDataSource ds = hikari(url);
        try {
            Map<String, Object> body = new DatabaseHealthController(ds).dbHealth();
            assertEquals("UP", body.get("status"));
            assertEquals("H2", body.get("product"), "getDatabaseProductName() 实测回「H2」，不是「Apache H2」");
            assertNotNull(body.get("productVersion"));

            @SuppressWarnings("unchecked")
            Map<String, Object> tables = (Map<String, Object>) body.get("tables");
            // H2 把未加引号标识符折成**大写**：按字面名探会得出「两张表都缺」的假红，
            // 这条断言就是那个大小写坑的守卫。
            assertEquals(Boolean.TRUE, tables.get("allPresent"), "实际 missing=" + tables.get("missing"));
            assertEquals(2, tables.get("expected"));
            assertTrue(((Integer) tables.get("scanned")) >= 2);

            @SuppressWarnings("unchecked")
            Map<String, Object> charset = (Map<String, Object>) body.get("charset");
            assertEquals(Boolean.FALSE, charset.get("applicable"), "列级字符集读数只在 MySQL 侧有意义");

            @SuppressWarnings("unchecked")
            Map<String, Object> pool = (Map<String, Object>) body.get("pool");
            assertEquals("hikari", pool.get("kind"));
            assertEquals("TestPool", pool.get("name"));
            assertEquals(4, pool.get("max"));
            assertEquals(1, pool.get("minIdle"));
            assertEquals(5000L, pool.get("connectionTimeoutMs"));
            assertNotNull(pool.get("active"), "取过连接之后必须能读到活水位");
            assertFalse(pool.containsKey("live"), "池已初始化却报 unverified = 读数丢了");
        } finally {
            ds.close();
        }
    }

    @Test
    @DisplayName("DOWN 侧：取连接必抛 ⇒ status=DOWN 且不抛（探测面自己不许成为故障源）")
    void downReportsError() {
        Map<String, Object> body = new DatabaseHealthController(broken()).dbHealth();
        assertEquals("DOWN", body.get("status"));
        assertEquals("IllegalStateException", body.get("error"));
        assertEquals("connection refused", body.get("reason"));
        @SuppressWarnings("unchecked")
        Map<String, Object> pool = (Map<String, Object>) body.get("pool");
        // 非 Hikari 实现：如实报 unverified，绝不编一个「0 条连接」出来
        assertEquals("unavailable", pool.get("metrics"));
    }

    @Test
    @DisplayName("冷启动侧：Hikari 池未初始化时读水位 ⇒ 报 unverified，不得让健康端点 500")
    void uninitializedPoolIsNotAnError() {
        HikariDataSource ds = hikari(freshUrl());
        try {
            Map<String, Object> pool = DatabaseHealthController.poolSnapshot(ds);
            assertEquals("hikari", pool.get("kind"));
            // 一次连接都没取过 ⇒ MXBean 不可用；这条腿要的是「有 live 键且值为 unverified 形态」，
            // 而不是把「还没建池」读成「池空着、一切正常」。
            assertTrue(String.valueOf(pool.getOrDefault("live", "")).startsWith("unverified"),
                    "实测 pool 读数=" + pool);
        } finally {
            ds.close();
        }
    }

    @Test
    @DisplayName("表缺失侧：没跑迁移的库 ⇒ allPresent=false 且点名缺哪两张（迁移没跑必须与跑过不同形）")
    void missingTablesAreNamed() {
        HikariDataSource ds = hikari(freshUrl());
        try {
            Map<String, Object> body = new DatabaseHealthController(ds).dbHealth();
            assertEquals("UP", body.get("status"), "库本身是活的，缺的只是表");
            @SuppressWarnings("unchecked")
            Map<String, Object> tables = (Map<String, Object>) body.get("tables");
            assertEquals(Boolean.FALSE, tables.get("allPresent"));
            @SuppressWarnings("unchecked")
            java.util.List<String> missing = (java.util.List<String>) tables.get("missing");
            assertEquals(2, missing.size(), "实际 missing=" + missing);
            assertTrue(missing.contains("chat_message"));
            assertTrue(missing.contains("emotion_record"));
        } finally {
            ds.close();
        }
    }

    @Test
    @DisplayName("脱敏：报错原文里的 password= 一律打星，长文截到 200 字；null/空串不得读成空消息")
    void safeMessageMasksAndCuts() {
        assertEquals("-", DatabaseHealthController.safeMessage(null));
        assertEquals("-", DatabaseHealthController.safeMessage(""));
        // 脱敏保留原大小写形态（PASSWORD=***），只把值打掉：改写键名会让运维对着
        // 一份「和本机配置不同名」的日志找参数。
        assertEquals("jdbc:mysql://h/db?user=root&PASSWORD=***",
                DatabaseHealthController.safeMessage("jdbc:mysql://h/db?user=root&PASSWORD=sekret"));
        String longText = "x".repeat(500);
        assertEquals(200, DatabaseHealthController.safeMessage(longText).length());
    }

    /**
     * MySQL 侧字符集读数（本机没有 MySQL 也能自证判据会红）。
     *
     * <p>这条腿不是凑覆盖：r130 那个缺口的**表现形态**就是「某些列不是 utf8mb4」。
     * 只在本机 H2 上跑过的健康面，永远证明不了「latin1 列能被点名」——
     * 所以用桩把 information_schema 的返回形状投进来，让「红该怎么红」在构建期就有回执。
     */
    @Test
    @DisplayName("charset·MySQL 形状：latin1 列必须被点名，全 utf8mb4 时才许报 allUtf8mb4=true")
    void charsetSnapshotOnMysqlShapeNamesOffenders() throws Exception {
        Connection c = mock(Connection.class);
        java.sql.Statement st = mock(java.sql.Statement.class);
        ResultSet rs = mock(ResultSet.class);
        when(c.createStatement()).thenReturn(st);
        when(st.executeQuery(anyString())).thenReturn(rs);
        // 三行：一行合格 utf8mb4、一行 latin1（r130 缺口的形状）、一行字符集读数为 null
        // （MySQL 对非字符列返回 NULL，例如 created_at）——null 那一支必须也走「点名」而不是漏判。
        when(rs.next()).thenReturn(true, true, true, false);
        when(rs.getString(1)).thenReturn("chat_message", "emotion_record", "emotion_record");
        when(rs.getString(2)).thenReturn("content", "text", "created_at");
        when(rs.getString(3)).thenReturn("utf8mb4", "latin1", null);
        when(rs.getString(4)).thenReturn("utf8mb4_unicode_ci", "latin1_swedish_ci", null);

        Map<String, Object> out = DatabaseHealthController.charsetSnapshot(c, "MySQL");
        assertEquals(Boolean.TRUE, out.get("applicable"));
        assertEquals(Boolean.TRUE, out.get("readable"));
        @SuppressWarnings("unchecked")
        java.util.List<String> offenders = (java.util.List<String>) out.get("nonUtf8mb4Columns");
        assertEquals(java.util.List.of("emotion_record.text=latin1", "emotion_record.created_at=null"),
                offenders, "非 utf8mb4 的列必须点名到列，只报「有问题」等于没报");
        assertEquals(Boolean.FALSE, out.get("allUtf8mb4"));
        assertEquals("utf8mb4_unicode_ci", out.get("collation"));

        // 对照：全部 utf8mb4 时必须全绿（否则这条判据就成了恒红的摆设）
        ResultSet clean = mock(ResultSet.class);
        when(clean.next()).thenReturn(true, false);
        when(clean.getString(1)).thenReturn("chat_message");
        when(clean.getString(2)).thenReturn("content");
        when(clean.getString(3)).thenReturn("utf8mb4");
        when(clean.getString(4)).thenReturn("utf8mb4_unicode_ci");
        when(st.executeQuery(anyString())).thenReturn(clean);
        Map<String, Object> ok = DatabaseHealthController.charsetSnapshot(c, "MySQL");
        assertEquals(Boolean.TRUE, ok.get("allUtf8mb4"));
        assertTrue(((java.util.List<?>) ok.get("nonUtf8mb4Columns")).isEmpty());
    }

    @Test
    @DisplayName("charset·读数取不到时如实报 readable=false，不得静默报全绿（探测失败≠没有失败）")
    void charsetSnapshotUnreadable() throws Exception {
        Connection c = mock(Connection.class);
        java.sql.Statement st = mock(java.sql.Statement.class);
        when(c.createStatement()).thenReturn(st);
        when(st.executeQuery(anyString())).thenThrow(new SQLException("no information_schema"));
        Map<String, Object> out = DatabaseHealthController.charsetSnapshot(c, "Percona Server (MySQL)");
        assertEquals(Boolean.FALSE, out.get("readable"));
        assertEquals("SQLException", out.get("error"));
        assertFalse(out.containsKey("allUtf8mb4"), "取不到读数时不得给出结论键");
    }

    @Test
    @DisplayName("charset·product 为 null 时走「不适用」分支而非 NPE")
    void charsetSnapshotNullProduct() throws Exception {
        Map<String, Object> out = DatabaseHealthController.charsetSnapshot(mock(Connection.class), null);
        assertEquals(Boolean.FALSE, out.get("applicable"));
    }

    @Test
    @DisplayName("池·MXBean 返回 null 时报 unverified（不得凭空造 0 条连接）")
    void poolSnapshotNullMxBean() {
        HikariDataSource h = mock(HikariDataSource.class);
        when(h.getPoolName()).thenReturn("Stub");
        when(h.getMaximumPoolSize()).thenReturn(8);
        when(h.getMinimumIdle()).thenReturn(2);
        when(h.getConnectionTimeout()).thenReturn(5000L);
        when(h.getMaxLifetime()).thenReturn(1740000L);
        when(h.getLeakDetectionThreshold()).thenReturn(20000L);
        when(h.getHikariPoolMXBean()).thenReturn(null);
        Map<String, Object> pool = DatabaseHealthController.poolSnapshot(h);
        assertEquals("hikari", pool.get("kind"));
        assertEquals(8, pool.get("max"));
        assertTrue(String.valueOf(pool.get("live")).startsWith("unverified"), "实测=" + pool);
        assertFalse(pool.containsKey("active"), "MXBean 为空却报活水位 = 编数据");
    }
}
