package com.xinyu.soulisle.config;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.dao.CannotAcquireLockException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.dao.DeadlockLoserDataAccessException;
import org.springframework.dao.PermissionDeniedDataAccessException;
import org.springframework.dao.QueryTimeoutException;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.CannotGetJdbcConnectionException;

import java.sql.SQLException;
import java.sql.SQLTimeoutException;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 数据库失败归因与降级出口（r169）。
 *
 * <p>为什么每类都要一条：六类归因各对应一种**不同的客户端处置**（重试 / 退避 / 回落本地存储 /
 * 直接判自己写得不对）。少一条用例，那一类就会在改动中被静默合并进 UNKNOWN，而 UNKNOWN
 * 的响应是 500 且 retryable=false —— 表现就是「库明明只是死锁了，客户端却再也不重试」。
 *
 * <p>取数面：Spring 翻译层给出的异常**类型**，与翻译层没插手时的**原始 SQLException vendor code**，
 * 两侧各自喂进去。后者不是假想：连接池借不到连接时抛的 {@code SQLTransientConnectionException}
 * 就直接冒到控制器（本项目 r130 那次的现场正是这一支）。
 */
class DbFailureTest {

    private static SQLException sql(int vendorCode, String state) {
        return new SQLException("boom", state, vendorCode);
    }

    @Test
    @DisplayName("归因·Spring 类型侧：死锁 / 超时 / 不可用 / 权限 / 数据被拒 各出一行，不共用一个分支")
    void classifySpringTypes() {
        assertEquals(DbFailure.DEADLOCK,
                DbFailure.classify(new DeadlockLoserDataAccessException("x", sql(1213, "40001"))));
        assertEquals(DbFailure.DEADLOCK,
                DbFailure.classify(new CannotAcquireLockException("x", sql(1205, "HY000"))));
        assertEquals(DbFailure.TIMEOUT,
                DbFailure.classify(new QueryTimeoutException("x", sql(3024, "HY000"))));
        assertEquals(DbFailure.UNAVAILABLE,
                DbFailure.classify(new DataAccessResourceFailureException("x", sql(2003, "HY000"))));
        assertEquals(DbFailure.UNAVAILABLE,
                DbFailure.classify(new CannotGetJdbcConnectionException("x", sql(2002, "08S01"))));
        assertEquals(DbFailure.FORBIDDEN,
                DbFailure.classify(new PermissionDeniedDataAccessException("x", sql(1045, "42000"))));
        assertEquals(DbFailure.REJECTED,
                DbFailure.classify(new DataIntegrityViolationException("x", sql(1406, "22001"))));
    }

    @Test
    @DisplayName("归因·死锁优先于超时：1205 与 1213 同为 HY000，只有 vendor code 能分开")
    void deadlockWinsOverLockWaitTimeout() {
        // CannotAcquireLockException 包 1205（锁等待超时）时按 Spring 语义归 DEADLOCK：
        // 这条断言把「谁先认领」钉住，改动顺序会立刻在这里红。
        assertEquals(DbFailure.DEADLOCK, DbFailure.classify(new CannotAcquireLockException("x", sql(1205, "HY000"))));
        // 同一条 1205 落在未翻译的原始 SQLException 上时归 TIMEOUT（翻译层没插手的那一支）。
        assertEquals(DbFailure.TIMEOUT, DbFailure.classify(sql(1205, "HY000")));
    }

    @Test
    @DisplayName("归因·原始 SQLException 侧：六类 vendor code 与两类 SQLState 各自落位")
    void classifyRawSqlException() {
        assertEquals(DbFailure.DEADLOCK, DbFailure.classify(sql(1213, "40001")));
        assertEquals(DbFailure.TIMEOUT, DbFailure.classify(sql(3024, "HY000")));
        assertEquals(DbFailure.FORBIDDEN, DbFailure.classify(sql(1044, "42000")));
        assertEquals(DbFailure.REJECTED, DbFailure.classify(sql(1062, "23000")));
        assertEquals(DbFailure.REJECTED, DbFailure.classify(sql(1366, "HY000")));
        assertEquals(DbFailure.REJECTED, DbFailure.classify(sql(1146, "42S02")));
        assertEquals(DbFailure.REJECTED, DbFailure.classify(sql(1054, "42S22")));
        assertEquals(DbFailure.REJECTED, DbFailure.classify(sql(1064, "42000")));
        assertEquals(DbFailure.UNAVAILABLE, DbFailure.classify(sql(0, "08S01")));
        assertEquals(DbFailure.UNAVAILABLE, DbFailure.classify(sql(2006, "HY000")));
    }

    @Test
    @DisplayName("归因·SQLTimeoutException 是超时而不是不可用（同一条链上只有它说得出「等满了」）")
    void sqlTimeoutIsTimeout() {
        assertEquals(DbFailure.TIMEOUT, DbFailure.classify(new SQLTimeoutException("too slow")));
    }

    @Test
    @DisplayName("归因·兜底三态：null 输入 / 非 SQL 异常 / SQL 异常但 code 认不出，都归 UNKNOWN 且不抛")
    void unknownBranches() {
        assertEquals(DbFailure.UNKNOWN, DbFailure.classify(null));
        assertEquals(DbFailure.UNKNOWN, DbFailure.classify(new IllegalStateException("not a db failure")));
        assertEquals(DbFailure.UNKNOWN, DbFailure.classify(sql(999999, "99999")));
        // 包装层：Spring 异常在链的**外层**、SQLException 在内层，也必须归得出来（上溯有界）
        assertEquals(DbFailure.REJECTED,
                DbFailure.classify(new RuntimeException("wrapper", new RuntimeException("mid", sql(1406, "22001")))));
    }

    @Test
    @DisplayName("归因·自引用因果链不得死循环：cause==this 时立刻停")
    void selfReferencingCauseStops() {
        SQLException loop = new SQLException("loop", "HY000", 0) {
            @Override
            public synchronized Throwable getCause() {
                return this;
            }
        };
        // 外层是普通异常、内层自引用：sqlOf 取不到任何可判的 SQL 码 ⇒ UNKNOWN，且必须在有限步内返回
        assertEquals(DbFailure.UNKNOWN, DbFailure.classify(new RuntimeException("outer", loop)));
        assertNull(DbFailure.sqlOf(new RuntimeException("no db error here")));
    }

    @Test
    @DisplayName("六类各配一个 HTTP 状态与 retryable：客户端据此选处置，禁两类同形")
    void statusAndRetryableTable() {
        assertEquals(503, DbFailure.UNAVAILABLE.status());
        assertTrue(DbFailure.UNAVAILABLE.retryable());
        assertEquals(409, DbFailure.DEADLOCK.status());
        assertTrue(DbFailure.DEADLOCK.retryable());
        assertEquals(504, DbFailure.TIMEOUT.status());
        assertTrue(DbFailure.TIMEOUT.retryable());
        assertEquals(403, DbFailure.FORBIDDEN.status());
        assertFalse(DbFailure.FORBIDDEN.retryable());
        assertEquals(422, DbFailure.REJECTED.status());
        assertFalse(DbFailure.REJECTED.retryable());
        assertEquals(500, DbFailure.UNKNOWN.status());
        assertFalse(DbFailure.UNKNOWN.retryable());
        assertEquals("db-unavailable", DbFailure.UNAVAILABLE.code());
    }

    @Test
    @DisplayName("降级出口·可重试类带 Retry-After，不可重试类不得带（否则教客户端去重试一个必败的请求）")
    void renderRetryAfter() {
        ResponseEntity<Map<String, Object>> retryable =
                DatabaseFailureAdvice.render(DbFailure.UNAVAILABLE, new DataAccessResourceFailureException("x", sql(2003, "HY000")));
        assertEquals(503, retryable.getStatusCode().value());
        assertEquals("2", retryable.getHeaders().getFirst("Retry-After"));
        assertEquals(Boolean.FALSE, retryable.getBody().get("ok"));
        assertEquals("db-unavailable", retryable.getBody().get("error"));
        assertEquals(Boolean.TRUE, retryable.getBody().get("retryable"));

        ResponseEntity<Map<String, Object>> final0 =
                DatabaseFailureAdvice.render(DbFailure.REJECTED, new DataIntegrityViolationException("x", sql(1406, "22001")));
        assertEquals(422, final0.getStatusCode().value());
        assertNull(final0.getHeaders().getFirst("Retry-After"));
        assertEquals(Boolean.FALSE, final0.getBody().get("retryable"));
        // 六类互不同形：状态码集合必须正好 6 个值
        assertEquals(6, java.util.Arrays.stream(DbFailure.values()).map(DbFailure::status).distinct().count());
    }

    @Test
    @DisplayName("降级出口·error 为 null 时日志分支不得抛（失败路径自己不能再成为故障源）")
    void renderWithNullError() {
        ResponseEntity<Map<String, Object>> r = DatabaseFailureAdvice.render(DbFailure.UNKNOWN, null);
        assertEquals(500, r.getStatusCode().value());
        assertEquals("db-error", r.getBody().get("error"));
    }

    @Test
    @DisplayName("降级出口·@ExceptionHandler 入口真跑一遍归因+渲染（防只测纯函数不测接线）")
    void handlerEntryIsWired() {
        DatabaseFailureAdvice advice = new DatabaseFailureAdvice();
        ResponseEntity<Map<String, Object>> r =
                advice.onDataAccess(new DeadlockLoserDataAccessException("x", sql(1213, "40001")));
        assertEquals(409, r.getStatusCode().value());
        assertEquals("db-deadlock", r.getBody().get("error"));
    }

    @Test
    @DisplayName("SQLState 为 null 时不得 NPE，也不得把「认不出」读成「连不上」")
    void nullSqlStateIsUnknown() {
        // 驱动在某些形态下（尤其包装过一层之后）只带 vendor code 不带 SQLState；
        // 这一支若 NPE，降级出口自己就成了 500 的来源。
        SQLException noState = new SQLException("bare", null, 0);
        assertEquals(DbFailure.UNKNOWN, DbFailure.classify(noState));
        assertEquals("db-error", DatabaseFailureAdvice.render(
                DbFailure.classify(noState), noState).getBody().get("error"));
    }

    @Test
    @DisplayName("2003 与 2006 是两个出口：连不上主机 vs 连接已断，都得归 UNAVAILABLE 且各自有一条腿")
    void bothConnectivityCodesMapToUnavailable() {
        assertEquals(DbFailure.UNAVAILABLE, DbFailure.classify(sql(2003, "HY000")));
        assertEquals(DbFailure.UNAVAILABLE, DbFailure.classify(sql(2006, "HY000")));
    }

    @Test
    @DisplayName("因果链超过上溯上限时必须在有限步内返回 UNKNOWN（不得死循环、不得栈溢出）")
    void deepCauseChainStopsAtBound() {
        Throwable chain = sql(1406, "22001");
        for (int i = 0; i < DbFailure.MAX_CAUSE_DEPTH + 3; i++) {
            chain = new RuntimeException("wrap" + i, chain);
        }
        // 目标码在链的**第 13 层**，超出上限 ⇒ 判「取不到」而落 UNKNOWN。
        // 这不是缺陷，是护栏：宁可归不进类，也不要在一个死循环里把请求线程搭进去。
        assertEquals(DbFailure.UNKNOWN, DbFailure.classify(chain));
    }
}
