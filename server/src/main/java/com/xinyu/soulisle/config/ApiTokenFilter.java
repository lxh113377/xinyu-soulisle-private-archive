package com.xinyu.soulisle.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * 可选轻量鉴权（J5）。
 *
 * <p>设计取舍：**不引入 Spring Security 全家桶** —— 本项目是对外演示的单体应用，
 * 需要的只是「私有部署时别让人随便打接口」。因此实现为一个可开关的 token 过滤器：
 * <ul>
 *   <li>{@code xinyu.api-token} 为空（默认）→ <b>完全放行</b>，v1/J1-J4 行为不变</li>
 *   <li>非空 → {@code /api/**}（除 {@code /api/health}）必须带 {@code X-Xinyu-Token}</li>
 * </ul>
 * 前端同源托管时不带该头，因此开启鉴权适用于「只暴露给受信客户端」的部署形态。
 */
@Component
public class ApiTokenFilter extends OncePerRequestFilter {

    /** 健康检查永远放行：负载均衡/容器探针不应因鉴权而失败 */
    private static final String OPEN_PATH = "/api/health";

    private final String token;

    public ApiTokenFilter(@Value("${xinyu.api-token:}") String token) {
        this.token = token == null ? "" : token.trim();
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String path = request.getRequestURI();
        boolean guarded = !token.isEmpty()
                && path.startsWith("/api/")
                && !OPEN_PATH.equals(path);

        if (guarded && !token.equals(request.getHeader("X-Xinyu-Token"))) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json");
            response.setCharacterEncoding(StandardCharsets.UTF_8.name());
            response.getWriter().write("{\"error\":\"unauthorized\"}");
            return;
        }
        chain.doFilter(request, response);
    }
}
