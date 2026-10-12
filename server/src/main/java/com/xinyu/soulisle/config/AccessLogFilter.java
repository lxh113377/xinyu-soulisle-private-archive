package com.xinyu.soulisle.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 结构化访问日志（r128 新增）。
 *
 * <p><b>为什么加</b>：此前全仓只有 {@code ModelProxy} 一处用了 slf4j，也就是
 * 「服务端对自己每分钟被打了多少次、花了多少毫秒」没有任何读数。排障时只能靠翻
 * 上游报错。对标面上 lobe-chat 仓里有 {@code packages/observability-otel} 与
 * {@code packages/llm-generation-tracing} 两个专门的包位。
 *
 * <p><b>红线</b>：只记**元数据**（路径、腿、状态、耗时、客户端），**绝不记请求体、
 * 响应体、Authorization 头与任何密钥** —— 密钥零落盘是本仓第一红线，
 * 日志同样是落盘。这条由 {@code _test/server_hardening_check.py} 常驻盯住。
 *
 * <p><b>订单</b>：{@code @Order(5)}，早于鉴权（10）与防护闸（20）⇒ 401 与 429 也在册。
 */
@Component
@Order(5)
public class AccessLogFilter extends OncePerRequestFilter {

    private static final org.slf4j.Logger LOGGER =
            org.slf4j.LoggerFactory.getLogger(AccessLogFilter.class);

    private final boolean enabled;

    private final AtomicLong total = new AtomicLong();
    private final AtomicLong overBudget = new AtomicLong();

    public AccessLogFilter(@Value("${xinyu.access-log.enabled:true}") boolean enabled) {
        this.enabled = enabled;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !request.getRequestURI().startsWith("/api/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        long start = System.nanoTime();
        try {
            chain.doFilter(request, response);
        } finally {
            long millis = (System.nanoTime() - start) / 1_000_000L;
            total.incrementAndGet();
            if (enabled) {
                // 超慢请求单独提级成 warn：这类行在正常量下稀少，混进 info 会被淹没
                String line = "{\"leg\":\"" + leg(request.getRequestURI())
                        + "\",\"method\":\"" + request.getMethod()
                        + "\",\"status\":" + response.getStatus()
                        + ",\"ms\":" + millis
                        + ",\"n\":" + total.get()
                        + "}";
                if (millis >= 1000) {
                    LOGGER.warn("access {}", line);
                    overBudget.incrementAndGet();
                } else {
                    LOGGER.info("access {}", line);
                }
            }
        }
    }

    /** 路径归成腿名：日志里不出现 sessionId 这类会随请求变化的片段，否则日志没法聚合 */
    static String leg(String uri) {
        if (uri == null) {
            return "unknown";
        }
        String[] parts = uri.split("/");
        if (parts.length >= 3 && "api".equals(parts[1])) {
            return "/api/" + parts[2];
        }
        return uri;
    }

    long count() {
        return total.get();
    }

    long slowCount() {
        return overBudget.get();
    }
}