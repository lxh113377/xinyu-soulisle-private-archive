package com.xinyu.soulisle.engine;

import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;
import java.net.InetAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 本地模型代理守卫：JDK HttpServer 回环桩（零新依赖/零公网/零密钥），仿 {@code LlmProxyTest}。
 *
 * <p>核心语义：**任何失败一律 null，不抛异常** —— 路由层拿到 null 自动降级下一腿，
 * 本地模型挂掉绝不能影响对话主链路。
 */
class ModelProxyTest {

    private HttpServer server;
    private final AtomicReference<String> lastBody = new AtomicReference<>();
    private final AtomicReference<Integer> lastStatus = new AtomicReference<>(200);
    private final AtomicReference<String> lastResp = new AtomicReference<>(
            "{\"emotion\":\"sadness\",\"intensity\":0.8,\"confidence\":0.93,\"latency_ms\":12.5}");

    @BeforeEach
    void setUp() throws IOException {
        server = HttpServer.create(new java.net.InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 0);
        server.createContext("/classify", ex -> {
            try (InputStream in = ex.getRequestBody()) {
                lastBody.set(new String(in.readAllBytes(), StandardCharsets.UTF_8));
            }
            byte[] resp = lastResp.get() == null ? new byte[0] : lastResp.get().getBytes(StandardCharsets.UTF_8);
            ex.getResponseHeaders().add("Content-Type", "application/json");
            ex.sendResponseHeaders(lastStatus.get(), resp.length == 0 ? -1 : resp.length);
            if (resp.length > 0) {
                ex.getResponseBody().write(resp);
            }
            ex.close();
        });
        server.start();
    }

    @AfterEach
    void tearDown() {
        server.stop(0);
    }

    private String baseUrl() {
        return "http://127.0.0.1:" + server.getAddress().getPort();
    }

    @Test
    @DisplayName("正常响应：三字段解析齐全，路径拼 /classify")
    void happyPath() {
        ModelProxy.Verdict v = new ModelProxy(baseUrl(), 1500).classify("论文被拒了三次，心里特别难过");
        assertEquals("sadness", v.emotion());
        assertEquals(0.8, v.intensity(), 1e-9);
        assertEquals(0.93, v.confidence(), 1e-9);
        assertTrue(lastBody.get().contains("\"text\":\"论文被拒了三次，心里特别难过\""), "请求体必须是 {\"text\":...}");
    }

    @Test
    @DisplayName("intensity 缺失取 0.5 中值（与 LLM 腿同规则），confidence 越界钳到 [0,1]")
    void defaultsAndClamp() {
        lastResp.set("{\"emotion\":\"joy\",\"confidence\":1.7}");
        ModelProxy.Verdict v = new ModelProxy(baseUrl(), 1500).classify("开心");
        assertEquals("joy", v.emotion());
        assertEquals(0.5, v.intensity(), 1e-9, "intensity 缺失 ⇒ 0.5 中值");
        assertEquals(1.0, v.confidence(), 1e-9, "confidence >1 钳到 1");
    }

    @Test
    @DisplayName("超长文本截断到 200 字（与 LLM 腿同规则）")
    void longTextTruncated() {
        ModelProxy proxy = new ModelProxy(baseUrl(), 1500);
        proxy.classify("长".repeat(300));
        assertTrue(lastBody.get().contains("\"text\":\"" + "长".repeat(200) + "\""),
                "text 值必须恰为前 200 字");
        assertTrue(!lastBody.get().contains("长".repeat(201)), "不得包含第 201 字");
    }

    @Test
    @DisplayName("四态失败全部 null 不抛：非 200 / 坏 JSON / 非法情绪名 / confidence 缺失")
    void failuresReturnNull() {
        ModelProxy proxy = new ModelProxy(baseUrl(), 1500);
        lastStatus.set(503);
        assertNull(proxy.classify("难过"), "非 200 必须 null");
        lastStatus.set(200);
        lastResp.set("<html>service down</html>");
        assertNull(proxy.classify("难过"), "坏 JSON 必须 null");
        lastResp.set("{\"emotion\":\"狂喜\",\"confidence\":0.9}");
        assertNull(proxy.classify("难过"), "情绪名不在六类枚举内必须 null");
        lastResp.set("{\"emotion\":\"joy\",\"intensity\":0.5}");
        assertNull(proxy.classify("难过"), "confidence 缺失/非数字必须 null");
        lastResp.set(null);
        assertNull(proxy.classify("难过"), "空响应体必须 null");
    }

    @Test
    @DisplayName("未配置 url：enabled=false，classify 直接 null 不发请求")
    void disabledWithoutUrl() {
        ModelProxy proxy = new ModelProxy("", 1500);
        assertFalse(proxy.enabled());
        assertNull(proxy.classify("难过"));
    }

    @Test
    @DisplayName("连不上（dead port）：null 不抛，路由层可安全降级")
    void deadEndpoint() {
        assertNull(new ModelProxy("http://127.0.0.1:1", 500).classify("难过"));
    }
}
