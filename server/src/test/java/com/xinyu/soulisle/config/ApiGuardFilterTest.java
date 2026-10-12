package com.xinyu.soulisle.config;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * r128：成本面/内存面防护闸的判据。
 *
 * <p>用 {@code MockHttpServletRequest/Response}，不起端口、不发公网请求 —— 与
 * {@code LlmProxyTest} 用 JDK HttpServer 回环桩是同一个「零外部依赖」取向。
 */
class ApiGuardFilterTest {

    private static MockHttpServletRequest post(String uri) {
        MockHttpServletRequest req = new MockHttpServletRequest("POST", uri);
        req.setRequestURI(uri);
        return req;
    }

    private static ApiGuardFilter guard(boolean enabled, int perMinute, int burst, long maxBody) {
        return new ApiGuardFilter(enabled, perMinute, burst, maxBody);
    }

    @Test
    @DisplayName("未超限的请求照常进业务链，且带剩余量响应头")
    void passesAndAnnouncesRemaining() throws Exception {
        ApiGuardFilter g = guard(true, 60, 20, 262144);
        MockHttpServletResponse resp = new MockHttpServletResponse();
        boolean[] reached = {false};

        g.doFilter(post("/api/chat"), resp, (r, s) -> reached[0] = true);

        assertTrue(reached[0], "未超限必须放行到业务链");
        assertEquals("60", resp.getHeader("X-RateLimit-Limit"));
        assertEquals("19", resp.getHeader("X-RateLimit-Remaining"), "取一个令牌后应剩 19");
    }

    @Test
    @DisplayName("打满桶后返回 429 + Retry-After，且不进业务链")
    void rejectsWhenExhausted() throws Exception {
        ApiGuardFilter g = guard(true, 60, 3, 262144);
        int[] reached = {0};
        MockHttpServletResponse last = new MockHttpServletResponse();

        for (int i = 0; i < 3; i++) {
            g.doFilter(post("/api/chat"), new MockHttpServletResponse(), (r, s) -> reached[0]++);
        }
        g.doFilter(post("/api/chat"), last, (r, s) -> reached[0]++);

        assertEquals(3, reached[0], "只有前三次进了业务链");
        assertEquals(429, last.getStatus());
        assertTrue(last.getHeader("Retry-After") != null, "429 必须给 Retry-After");
        assertTrue(Integer.parseInt(last.getHeader("Retry-After")) >= 1, "Retry-After 至少 1 秒");
        assertEquals("{\"error\":\"rate-limited\"}", last.getContentAsString());
    }

    @Test
    @DisplayName("不同客户端各算各的桶：一方打满不牵连另一方")
    void bucketsAreIsolatedPerClient() throws Exception {
        ApiGuardFilter g = guard(true, 60, 1, 262144);
        MockHttpServletRequest a = post("/api/chat");
        a.setRemoteAddr("10.0.0.1");
        MockHttpServletRequest b = post("/api/chat");
        b.setRemoteAddr("10.0.0.2");

        g.doFilter(a, new MockHttpServletResponse(), (r, s) -> { });
        MockHttpServletResponse bResp = new MockHttpServletResponse();
        boolean[] bReached = {false};
        g.doFilter(b, bResp, (r, s) -> bReached[0] = true);

        assertTrue(bReached[0], "另一个 IP 的首个请求不该被牵连");
        assertEquals(200, bResp.getStatus());
    }

    @Test
    @DisplayName("X-Forwarded-For 取第一跳作为分桶键")
    void usesFirstForwardedHop() {
        ApiGuardFilter g = guard(true, 60, 20, 262144);
        MockHttpServletRequest req = post("/api/chat");
        req.addHeader("X-Forwarded-For", "203.0.113.7, 10.1.1.1, 10.2.2.2");
        assertEquals("203.0.113.7", g.clientKey(req));

        MockHttpServletRequest noHeader = post("/api/chat");
        noHeader.setRemoteAddr("192.0.2.9");
        assertEquals("192.0.2.9", g.clientKey(noHeader));
    }

    @Test
    @DisplayName("超体请求 413，且在限流判定之前就挡掉")
    void rejectsOversizedBody() throws Exception {
        ApiGuardFilter g = guard(true, 60, 20, 100);
        MockHttpServletRequest req = post("/api/chat");
        req.addHeader("Content-Length", "101");
        MockHttpServletResponse resp = new MockHttpServletResponse();
        boolean[] reached = {false};

        g.doFilter(req, resp, (r, s) -> reached[0] = true);

        assertFalse(reached[0], "超体请求不得进业务链");
        assertEquals(413, resp.getStatus());
        assertEquals("{\"error\":\"payload-too-large\"}", resp.getContentAsString());
        assertEquals("100", resp.getHeader("X-Xinyu-Body-Limit"));
    }

    @Test
    @DisplayName("chunked（无 Content-Length）不误判为超体")
    void chunkedBodyIsNotRejected() throws Exception {
        ApiGuardFilter g = guard(true, 60, 20, 100);
        MockHttpServletRequest req = post("/api/chat");
        assertEquals(-1L, g.declaredLength(req), "缺 Content-Length 时应是「判不了」而不是「判为 0」");
        MockHttpServletResponse resp = new MockHttpServletResponse();
        boolean[] reached = {false};
        g.doFilter(req, resp, (r, s) -> reached[0] = true);
        assertTrue(reached[0], "判不了的请求应放行，而不是被当成超体");
        assertEquals(200, resp.getStatus());
    }

    @Test
    @DisplayName("非法 Content-Length 不抛栈，按判不了处理")
    void malformedContentLengthIsSafe() {
        ApiGuardFilter g = guard(true, 60, 20, 100);
        MockHttpServletRequest req = post("/api/chat");
        req.addHeader("Content-Length", "not-a-number");
        assertEquals(-1L, g.declaredLength(req));
    }

    @Test
    @DisplayName("health 永不受限：探针连打 200 次也不该被 429")
    void healthIsNeverGuarded() throws Exception {
        ApiGuardFilter g = guard(true, 1, 1, 262144);
        int ok = 0;
        for (int i = 0; i < 200; i++) {
            MockHttpServletResponse resp = new MockHttpServletResponse();
            g.doFilter(post("/api/health"), resp, (r, s) -> { });
            if (resp.getStatus() == 200) {
                ok++;
            }
        }
        assertEquals(200, ok);
    }

    @Test
    @DisplayName("静态页不经这道闸：shouldNotFilter 只拦 /api/")
    void staticPathsBypassGuard() {
        ApiGuardFilter g = guard(true, 60, 20, 262144);
        assertFalse(g.shouldNotFilter(post("/api/chat")));
        assertTrue(g.shouldNotFilter(post("/index.html")));
        assertTrue(g.shouldNotFilter(post("/js/app.js")));
    }

    @Test
    @DisplayName("enabled=false 或 per-minute=0 都退化成不限流（应急逃生阀）")
    void canBeDisabled() throws Exception {
        for (ApiGuardFilter g : new ApiGuardFilter[]{
                guard(false, 1, 1, 262144), guard(true, 0, 1, 262144)}) {
            MockHttpServletResponse resp = new MockHttpServletResponse();
            for (int i = 0; i < 50; i++) {
                g.doFilter(post("/api/chat"), resp, (r, s) -> { });
            }
            assertEquals(200, resp.getStatus(), "关闭后不该出现 429");
        }
    }

    @Test
    @DisplayName("max-body 配成 0 时等于不限体（不是「上限 0 字节」那种反向坑）")
    void zeroMaxBodyMeansUnlimited() throws Exception {
        ApiGuardFilter g = guard(true, 60, 20, 0);
        MockHttpServletRequest req = post("/api/chat");
        req.addHeader("Content-Length", "999999999");
        MockHttpServletResponse resp = new MockHttpServletResponse();
        boolean[] reached = {false};
        g.doFilter(req, resp, (r, s) -> reached[0] = true);
        assertTrue(reached[0], "配 0 应解释为不限体");
    }

    @Test
    @DisplayName("缺客户端地址时退化成共享桶的 unknown 键，不抛 NPE")
    void nullRemoteAddrIsSafe() {
        ApiGuardFilter g = guard(true, 60, 20, 262144);
        MockHttpServletRequest req = post("/api/chat");
        req.setRemoteAddr(null);   // Mock 默认给 127.0.0.1，得显式置空才测到 null 那条分支
        assertEquals("unknown", g.clientKey(req));
    }
}