package com.xinyu.soulisle;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 心屿 SoulIsle 服务端入口。
 *
 * <p>J1 职责边界：托管现有前端静态页（权威源 {@code src/}，直读不做副本）+ 暴露 {@code /api/health}。
 * 业务 API（{@code /api/chat}）在 J2 接入，届时前端只需换 baseURL。
 */
@SpringBootApplication
public class SoulIsleApplication {

    public static void main(String[] args) {
        SpringApplication.run(SoulIsleApplication.class, args);
    }
}
