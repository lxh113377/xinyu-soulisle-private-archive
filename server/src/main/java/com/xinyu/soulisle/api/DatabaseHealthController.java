package com.xinyu.soulisle.api;

import com.zaxxer.hikari.HikariDataSource;
import com.zaxxer.hikari.HikariPoolMXBean;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 数据库面自证（r169）：{@code GET /api/health/db}。
 *
 * <p>为什么不并进 {@code /api/health}：① {@code HealthController} 被性能判据高频打，
 * 在那里加一次真连库往返会把「服务本身」的读数变成「库」的读数；② 既有验收标准 AC-OBS-07
 * 断言的是 health 的静态面字段，加一格 DB 会让那条断言的取数面悄悄变化。所以另开一面。
 *
 * <p>要回答的问题：修前 {@code /api/health} 在**库完全连不上**时仍回 {@code status=UP}
 * （它只看 index.html 与 vendor 目录），于是「服务起来了但持久化整面是死的」这件事
 * 在健康面上不可见 —— 这正是「优雅降级」缺的那块输入：客户端得先知道库死了才谈得上回落。
 *
 * <p>本件**永不抛**：探测自身失败就是它要报告的内容，抛出去反而把唯一一次读数机会弄丢。
 *
 * <p>鉴权：走 {@code ApiTokenFilter} 的默认护栏 —— 该类只对 {@code /api/health} 精确放行，
 * 故配了 {@code xinyu.api-token} 时本端点**需要带 token**（它回吐库版本、字符集、池水位，
 * 属运维信息，不该比业务接口更开放）。
 */
@RestController
public class DatabaseHealthController {

    private static final String[] EXPECTED_TABLES = {"chat_message", "emotion_record"};

    private final DataSource dataSource;

    public DatabaseHealthController(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    @GetMapping("/api/health/db")
    public Map<String, Object> dbHealth() {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("service", "xinyu-soulisle");
        long startedAt = System.nanoTime();
        try (Connection c = dataSource.getConnection()) {
            body.put("status", "UP");
            body.put("acquireMs", elapsedMs(startedAt));
            DatabaseMetaData md = c.getMetaData();
            body.put("product", md.getDatabaseProductName());
            body.put("productVersion", md.getDatabaseProductVersion());
            body.put("driver", md.getDriverName());
            body.put("tables", tableSnapshot(c, md));
            body.put("charset", charsetSnapshot(c, md.getDatabaseProductName()));
        } catch (Exception e) {
            body.put("status", "DOWN");
            body.put("acquireMs", elapsedMs(startedAt));
            body.put("error", e.getClass().getSimpleName());
            body.put("reason", safeMessage(e.getMessage()));
        }
        // 池水位放在取连接**之后**读：HikariCP 惰性建池，先读会把刚初始化好的池报成 unverified。
        body.put("pool", poolSnapshot());
        return body;
    }

    /** 池水位只在 Hikari 上取得到；换实现（演示用的极简池/测试桩）时如实报未取到，不猜。 */
    static Map<String, Object> poolSnapshot(DataSource ds) {
        Map<String, Object> pool = new LinkedHashMap<>();
        if (!(ds instanceof HikariDataSource)) {
            pool.put("kind", ds.getClass().getSimpleName());
            pool.put("metrics", "unavailable");
            return pool;
        }
        HikariDataSource hikari = (HikariDataSource) ds;
        pool.put("kind", "hikari");
        pool.put("name", hikari.getPoolName());
        pool.put("max", hikari.getMaximumPoolSize());
        pool.put("minIdle", hikari.getMinimumIdle());
        pool.put("connectionTimeoutMs", hikari.getConnectionTimeout());
        pool.put("maxLifetimeMs", hikari.getMaxLifetime());
        pool.put("leakDetectionThresholdMs", hikari.getLeakDetectionThreshold());
        // 活水位：active/idle/waiting 是「池被打满」的唯一现场证据，而池打满在高并发下的表现
        // 就是接口挂到 connectionTimeout 然后失败。
        // ⚠️ 这一段**必须整个包在 try 里**：HikariCP 的池是**取第一次连接时才惰性初始化**，
        // 未初始化时 getHikariPoolMXBean() 抛 IllegalStateException。健康端点若在冷启动时就
        // 因为读水位而 500，那它就把「服务正常、库正常」一起报丢了 —— 探测面自己成为故障源。
        try {
            HikariPoolMXBean bean = hikari.getHikariPoolMXBean();
            if (bean != null) {
                pool.put("active", bean.getActiveConnections());
                pool.put("idle", bean.getIdleConnections());
                pool.put("total", bean.getTotalConnections());
                pool.put("waiting", bean.getThreadsAwaitingConnection());
            } else {
                pool.put("live", "unverified（MXBean 返回 null）");
            }
        } catch (RuntimeException e) {
            // 池尚未初始化（还没取过连接）—— 这不是错误，但绝不能读成「0 条连接、一切正常」。
            pool.put("live", "unverified（" + e.getClass().getSimpleName() + "）");
        }
        return pool;
    }

    private Map<String, Object> poolSnapshot() {
        return poolSnapshot(dataSource);
    }

    /** 表存在性 + 行数下限：迁移没跑与迁移跑过在这里必须不同形。 */
    private static Map<String, Object> tableSnapshot(Connection c, DatabaseMetaData md) throws Exception {
        // 一次列全表、按**大小写不敏感**比对，而不是 getTables(name) 逐张探：
        // H2 会把未加引号的标识符折成**大写**（CHAT_MESSAGE），而 MySQL 在 Linux 上区分大小写、
        // 在 Windows 上按建表原样存。按字面名精确探会在 H2 侧得到「两张表都缺」的假红。
        List<String> found = new ArrayList<>();
        try (ResultSet rs = md.getTables(c.getCatalog(), null, "%", new String[]{"TABLE"})) {
            while (rs.next()) {
                found.add(rs.getString(3));
            }
        }
        List<String> missing = new ArrayList<>();
        for (String table : EXPECTED_TABLES) {
            if (found.stream().noneMatch(table::equalsIgnoreCase)) {
                missing.add(table);
            }
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("expected", EXPECTED_TABLES.length);
        out.put("scanned", found.size());
        out.put("missing", missing);
        out.put("allPresent", missing.isEmpty());
        return out;
    }

    /**
     * 字符集读数只在 MySQL 有意义：列的实际字符集由**建表时**的 DEFAULT CHARSET 决定，
     * 而 r130 那条已证未修的缺口正是「建表语句没写、于是跟随服务器默认」。
     * 这里读的是 information_schema 的**列级**读数，不是服务器变量 —— 因为判据要问的是
     * 「这两张表在这台服务器上到底是 utf8mb4 还是 latin1」。
     *
     * <p>包内可见（seam）：本机没有 MySQL 时也要能把「列是 latin1」这个形状喂进来自证判据
     * 会红。与 {@code HealthController.resolveSource} 同一先例——纯逻辑拆出来才测得到那几支。
     */
    static Map<String, Object> charsetSnapshot(Connection c, String product) {
        Map<String, Object> out = new LinkedHashMap<>();
        if (product == null || !product.toLowerCase().contains("mysql")) {
            out.put("applicable", false);
            out.put("note", "非 MySQL（" + product + "），列级字符集读数不适用");
            return out;
        }
        out.put("applicable", true);
        List<String> nonUtf8mb4 = new ArrayList<>();
        try (Statement st = c.createStatement();
             ResultSet rs = st.executeQuery(
                     "SELECT TABLE_NAME, COLUMN_NAME, CHARACTER_SET_NAME, COLLATION_NAME "
                             + "FROM information_schema.COLUMNS "
                             + "WHERE TABLE_SCHEMA = DATABASE() "
                             + "AND TABLE_NAME IN ('chat_message','emotion_record') "
                             + "AND CHARACTER_SET_NAME IS NOT NULL")) {
            while (rs.next()) {
                // 每行都把「表.列」读出来再判字符集：读列名不是额外成本（同一行、同一次结果集），
                // 却让「点名」这件事在所有分支上都成立 —— 只在失败时才拼标签的写法，
                // 会把「哪一列出问题」和「有没有问题」两套取数顺序混在一起，桩也很难投准。
                String column = rs.getString(1) + "." + rs.getString(2);
                String charset = rs.getString(3);
                if (charset == null || !"utf8mb4".equalsIgnoreCase(charset)) {
                    nonUtf8mb4.add(column + "=" + charset);
                }
                out.putIfAbsent("collation", rs.getString(4));
            }
        } catch (Exception e) {
            out.put("readable", false);
            out.put("error", e.getClass().getSimpleName());
            return out;
        }
        out.put("readable", true);
        out.put("nonUtf8mb4Columns", nonUtf8mb4);
        out.put("allUtf8mb4", nonUtf8mb4.isEmpty());
        return out;
    }

    private static long elapsedMs(long startedAtNanos) {
        return (System.nanoTime() - startedAtNanos) / 1_000_000L;
    }

    /** 报错原文可能含 JDBC URL（内网主机名）；只留前 200 字并脱敏口令形态。 */
    static String safeMessage(String raw) {
        if (raw == null || raw.isEmpty()) {
            return "-";
        }
        String cut = raw.length() <= 200 ? raw : raw.substring(0, 200);
        return cut.replaceAll("(?i)(password|pwd)=[^;&\\s]+", "$1=***");
    }
}
