package com.xinyu.soulisle.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.sql.SQLException;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 数据库失败的**降级出口**（r169）：把 {@link DataAccessException} 收成一个结构化、可判定、
 * 且告诉调用方「这次该不该重试」的 JSON，而不是让 Spring 默认的 /error 页面带着堆栈出去。
 *
 * <p>修前实测形态：{@code MemoryController} 全文零 {@code DataAccessException} 处理
 * （grep {@code @ExceptionHandler|ControllerAdvice} 在 server/src/main/java 下 0 命中），
 * 库不可达时客户端拿到的是 Spring 白标 500 —— 于是「服务端挂了」与「我这个请求写得不对」
 * 在响应上完全同形，前端既不能退回本地存储，判据也没法断言降级是否发生。
 *
 * <p>边界：只处理数据访问层异常。既有契约（{@code bad-json} 400、{@code no-key} 500 等）
 * 由各控制器自己返回，本件不接管，避免把 LLM 链路的错误体口径一起改掉。
 */
@RestControllerAdvice
public class DatabaseFailureAdvice {

    private static final Logger log = LoggerFactory.getLogger(DatabaseFailureAdvice.class);

    /** 可重试类失败给浏览器的退避建议（秒）。写死一个小值而不是指数退避：客户端只有一份。 */
    static final int RETRY_AFTER_SECONDS = 2;

    @ExceptionHandler(DataAccessException.class)
    public ResponseEntity<Map<String, Object>> onDataAccess(DataAccessException error) {
        return render(DbFailure.classify(error), error);
    }

    /**
     * 拆成独立方法以便构建期直接喂六类归因结果，不必为每个分支起一个真库。
     *
     * <p>日志只取「归因 + vendor code + 异常类名」，不打整段堆栈：这类事件在库挂掉时是
     * **每个请求一条**，堆栈会把访问日志面淹掉，而堆栈里能多出来的信息只有驱动内部帧。
     */
    static ResponseEntity<Map<String, Object>> render(DbFailure failure, Throwable error) {
        SQLException sql = DbFailure.sqlOf(error);
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("ok", false);
        body.put("error", failure.code());
        body.put("retryable", failure.retryable());

        ResponseEntity.BodyBuilder builder = ResponseEntity.status(failure.status())
                .contentType(MediaType.APPLICATION_JSON);
        if (failure.retryable()) {
            builder = builder.header("Retry-After", String.valueOf(RETRY_AFTER_SECONDS));
        }
        log.warn("db-failure class={} code={} status={} retryable={} sqlState={} vendor={}",
                error == null ? "-" : error.getClass().getSimpleName(),
                failure.code(), failure.status(), failure.retryable(),
                sql == null ? "-" : sql.getSQLState(),
                sql == null ? "-" : sql.getErrorCode());
        return builder.body(body);
    }
}
