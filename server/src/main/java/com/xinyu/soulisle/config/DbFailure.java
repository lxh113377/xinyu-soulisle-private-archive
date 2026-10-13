package com.xinyu.soulisle.config;

import org.springframework.dao.CannotAcquireLockException;
import org.springframework.dao.ConcurrencyFailureException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.dao.PermissionDeniedDataAccessException;
import org.springframework.dao.QueryTimeoutException;
import org.springframework.dao.TransientDataAccessResourceException;

import java.sql.SQLException;

/**
 * 数据库失败的**归因分类**（r169）。
 *
 * <p>为什么要有这一层：Objective 里那句「连接异常、死锁、超时时系统能优雅降级」，在实现上
 * 不是一个 catch 能覆盖的形态 —— 这三类的**正确处置完全不同**：
 * <ul>
 *   <li>死锁（1213）：事务被 MySQL 主动挑掉一个，**重试就有**，不该对用户报 5xx；</li>
 *   <li>锁等待超时（1205）/查询超时：是预算问题，重试要看次数，且值得先等一小会儿；</li>
 *   <li>连不上（08S01 / 2003 / 池借不到连接）：整个持久面不可用，前端应当回落本地存储；</li>
 *   <li>数据被拒（1406 too long / 1366 incorrect string value / 1062 dup）：**重试一万次也不会成**，
 *       把它归到「数据库不可用」就是掩盖一个真实缺陷 —— 1366 恰好就是字符集没修对时的那个出口。</li>
 * </ul>
 * 混成一个 500 的话，判据侧和用户侧都读不出是哪一类，降级路径也无从选择。
 *
 * <p>本类只做**归因**（纯函数，零 IO、零 Spring 上下文），HTTP 状态与响应体在
 * {@link DatabaseFailureAdvice}。拆开是为了让四类各有独立用例，而不是让测试去起一个真库。
 */
public enum DbFailure {

    /** 持久面整体不可用：连接失败 / 池借不到连接 / 实例挂了。 */
    UNAVAILABLE("db-unavailable", 503, true),
    /** 死锁：MySQL 已主动回滚本事务，重试语义安全。 */
    DEADLOCK("db-deadlock", 409, true),
    /** 超时：锁等待超时或查询超时。 */
    TIMEOUT("db-timeout", 504, true),
    /** 权限：账号无权访问该库/表。重试无用，属部署配置问题。 */
    FORBIDDEN("db-forbidden", 403, false),
    /** 数据被服务端拒绝：列宽、字符集、唯一约束。重试无用，是调用方或 DDL 的缺陷。 */
    REJECTED("db-rejected", 422, false),
    /** 归不进以上任何一类 —— 如实保留，不假装知道。 */
    UNKNOWN("db-error", 500, false);

    /** 因果链最多上溯这么多层：足够穿过 Spring→JDBC→驱动三层包装，又不会在自引用链上死循环。 */
    static final int MAX_CAUSE_DEPTH = 10;

    private final String code;
    private final int status;
    private final boolean retryable;

    DbFailure(String code, int status, boolean retryable) {
        this.code = code;
        this.status = status;
        this.retryable = retryable;
    }

    public String code() {
        return code;
    }

    public int status() {
        return status;
    }

    public boolean retryable() {
        return retryable;
    }

    /**
     * 归因入口。先按 Spring 的异常语义判（翻译层已经把 vendor code 消化过一轮），
     * Spring 层判不出来再直接看因果链里的 {@link SQLException} vendor code —— 因为
     * 连接池与驱动在某些形态下抛出的是**未被翻译**的原始 SQLException。
     *
     * <p>顺序即优先级，且**每类各一个出口**（不共用一个 catch）：死锁排在超时之前，
     * 因为 1205/1213 在 SQLState 上同为 HY000，只有 vendor code 能分开。
     */
    public static DbFailure classify(Throwable error) {
        if (error == null) {
            return UNKNOWN;
        }
        // 1) 死锁必须先判：DeadlockLoser 与 CannotAcquireLock 都是 ConcurrencyFailure 的子族
        if (isDeadlock(error)) {
            return DEADLOCK;
        }
        // 2) 超时
        if (isTimeout(error)) {
            return TIMEOUT;
        }
        // 3) 权限（在「不可用」之前：1045 也是连接期失败，但它不是「挂了」，是「没配好」）
        if (error instanceof PermissionDeniedDataAccessException) {
            return FORBIDDEN;
        }
        // 4) 资源不可用
        if (error instanceof DataAccessResourceFailureException
                || error instanceof TransientDataAccessResourceException) {
            return UNAVAILABLE;
        }
        // 5) 数据被拒（排在最后：DataIntegrityViolation 与「列跟着错误的服务器默认字符集」同出口，
        //    误判成不可用会掩盖真缺陷，所以宁可让上面四类先各自认领）
        if (error instanceof DataIntegrityViolationException) {
            return REJECTED;
        }
        // 6) Spring 层判不出来时按 vendor code 兜底
        return byVendorCode(error);
    }

    private static boolean isDeadlock(Throwable error) {
        if (error instanceof CannotAcquireLockException || error instanceof ConcurrencyFailureException) {
            return true;
        }
        SQLException sql = sqlOf(error);
        return sql != null && sql.getErrorCode() == MySQLCodes.DEADLOCK;
    }

    private static boolean isTimeout(Throwable error) {
        if (error instanceof QueryTimeoutException) {
            return true;
        }
        SQLException sql = sqlOf(error);
        if (sql == null) {
            return false;
        }
        if (sql instanceof java.sql.SQLTimeoutException) {
            return true;
        }
        int code = sql.getErrorCode();
        return code == MySQLCodes.LOCK_WAIT_TIMEOUT;
    }

    /** vendor code / SQLState 兜底：仅在 Spring 翻译层没插手（原始 SQLException 直冒）时才有活。 */
    private static DbFailure byVendorCode(Throwable error) {
        SQLException sql = sqlOf(error);
        if (sql == null) {
            return UNKNOWN;
        }
        int code = sql.getErrorCode();
        if (code == MySQLCodes.DEADLOCK) {
            return DEADLOCK;
        }
        if (code == MySQLCodes.LOCK_WAIT_TIMEOUT || code == MySQLCodes.MAX_EXECUTION_TIME) {
            return TIMEOUT;
        }
        if (code == MySQLCodes.ACCESS_DENIED || code == MySQLCodes.NO_ACCESS_FOR_USER) {
            return FORBIDDEN;
        }
        if (code == MySQLCodes.PARSE_ERROR || code == MySQLCodes.NO_SUCH_TABLE
                || code == MySQLCodes.UNKNOWN_COLUMN) {
            // 语法 / 表不存在(1146) / 列不存在(1054)：不是运行时故障，是**代码与库结构脱节**。
            // 归 REJECTED 而非 UNKNOWN，因为「Unknown column」正是「迁移没跑」的那个出口，
            // 判成 500 会把它藏进「服务内部错误」里，而它其实是一条该立刻看见的部署缺陷。
            return REJECTED;
        }
        if (code == MySQLCodes.DUP_ENTRY || code == MySQLCodes.DATA_TOO_LONG
                || code == MySQLCodes.INCORRECT_STRING_VALUE) {
            return REJECTED;
        }
        String state = sql.getSQLState() == null ? "" : sql.getSQLState();
        if (state.startsWith("08")) {
            // 08S01/08001/08004：连接异常类（driver 层）
            return UNAVAILABLE;
        }
        if (state.startsWith("HY000") && (code == MySQLCodes.COMMS_LINK_FAILURE
                || code == MySQLCodes.CANT_CONNECT)) {
            return UNAVAILABLE;
        }
        return UNKNOWN;
    }

    /** 有界上溯因果链找 SQLException；自引用/超长链一律停，不抛。 */
    static SQLException sqlOf(Throwable error) {
        Throwable cur = error;
        for (int depth = 0; cur != null && depth < MAX_CAUSE_DEPTH; depth++) {
            if (cur instanceof SQLException) {
                return (SQLException) cur;
            }
            Throwable next = cur.getCause();
            if (next == cur) {
                break;
            }
            cur = next;
        }
        return null;
    }

    /** MySQL vendor code 常量表（数值取自官方 ER 错误码，非猜测）。 */
    static final class MySQLCodes {
        static final int DUP_ENTRY = 1062;
        static final int NO_ACCESS_FOR_USER = 1044;
        static final int ACCESS_DENIED = 1045;
        static final int PARSE_ERROR = 1064;
        static final int NO_SUCH_TABLE = 1146;
        static final int UNKNOWN_COLUMN = 1054;
        static final int DEADLOCK = 1213;
        static final int LOCK_WAIT_TIMEOUT = 1205;
        static final int MAX_EXECUTION_TIME = 3024;
        static final int DATA_TOO_LONG = 1406;
        static final int INCORRECT_STRING_VALUE = 1366;
        static final int COMMS_LINK_FAILURE = 2006;
        static final int CANT_CONNECT = 2003;

        private MySQLCodes() {
        }
    }
}
