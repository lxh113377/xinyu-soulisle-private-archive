package com.xinyu.soulisle.config;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import java.time.Clock;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * r130：总量闸的横切接线判据。与 {@link ApiGuardFilterTest} 同款取向 ——
 * {@code MockHttpServletRequest/Response}，不起端口、不发公网请求。
 */
class QuotaFilterTest {

    private static MockHttpServletRequest post(String uri, String body) {
        MockHttpServletRequest req = new MockHttpServletRequest("POST", uri);
        req.setRequestURI(uri);
        if (body != null) {
            req.setContent(body.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            req.addHeader("Content-Length", String.valueOf(body.getBytes(java.nio.charset.StandardCharsets.UTF_8).length));
        }
        return req;
    }

    private static QuotaFilter filter(boolean enabled, Set<String> paths, long dailyRequests, long dailyTokens) {
        return new QuotaFilter(enabled, paths, new UsageLedger(Clock.systemDefaultZone(), dailyRequests, dailyTokens));
    }

    @Test
    @DisplayName("计量路径放行并回 X-Quota-Day-Used / Limit 头")
    void meteredPathAnnouncesQuota() throws Exception {
        QuotaFilter f = filter(true, Set.of("/api/chat"), 10, 0);
        MockHttpServletResponse resp = new MockHttpServletResponse();
        boolean[] reached = {false};

        f.doFilter(post("/api/chat", "{\"messages\":[]}"), resp, (r, s) -> reached[0] = true);

        assertTrue(reached[0], "未达日额必须进业务链");
        assertEquals("1", resp.getHeader("X-Quota-Day-Used"));
        assertEquals("10", resp.getHeader("X-Quota-Day-Limit"));
    }

    @Test
    @DisplayName("日额打满 → 429 + Retry-After，且不进业务链")
    void rejectsWhenDailyQuotaExhausted() throws Exception {
        QuotaFilter f = filter(true, Set.of("/api/chat"), 2, 0);
        int[] reached = {0};
        f.doFilter(post("/api/chat", "{}"), new MockHttpServletResponse(), (r, s) -> reached[0]++);
        f.doFilter(post("/api/chat", "{}"), new MockHttpServletResponse(), (r, s) -> reached[0]++);

        MockHttpServletResponse last = new MockHttpServletResponse();
        f.doFilter(post("/api/chat", "{}"), last, (r, s) -> reached[0]++);

        assertEquals(2, reached[0], "只有前两次进了业务链");
        assertEquals(429, last.getStatus());
        assertEquals("{\"error\":\"daily-quota-exceeded\"}", last.getContentAsString());
        assertTrue(Integer.parseInt(last.getHeader("Retry-After")) >= 1);
        assertEquals("2", last.getHeader("X-Quota-Day-Used"), "拒绝时也要如实回累计，便于调用方判断");
    }

    @Test
    @DisplayName("非计量路径不计数、不受限（日额只盯真花钱的端点）")
    void unmeteredPathPassesFree() throws Exception {
        QuotaFilter f = filter(true, Set.of("/api/chat"), 1, 0);
        MockHttpServletRequest emo = post("/api/emotion", "{\"text\":\"hi\"}");
        boolean[] reached = {false};
        MockHttpServletResponse resp = new MockHttpServletResponse();

        f.doFilter(emo, resp, (r, s) -> reached[0] = true);

        assertTrue(reached[0]);
        assertNull(resp.getHeader("X-Quota-Day-Used"), "不计量就不该给用量头，免得被误读成已计费");
        assertEquals(0, f.snapshot().requests());
    }

    @Test
    @DisplayName("enabled=false 是整个闸的逃生阀：完全放行且不计数")
    void disabledIsEscapeHatch() throws Exception {
        QuotaFilter f = filter(false, Set.of("/api/chat"), 1, 0);
        MockHttpServletResponse resp = new MockHttpServletResponse();
        boolean[] reached = {false};

        f.doFilter(post("/api/chat", "{}"), resp, (r, s) -> reached[0] = true);

        assertTrue(reached[0]);
        assertNull(resp.getHeader("X-Quota-Day-Used"));
        assertEquals(0, f.snapshot().requests());
    }

    @Test
    @DisplayName("chunked（无 Content-Length）按 0 token 计，不阻塞业务")
    void chunkedRequestStillMetered() throws Exception {
        QuotaFilter f = filter(true, Set.of("/api/chat"), 5, 0);
        MockHttpServletRequest req = new MockHttpServletRequest("POST", "/api/chat");
        req.setRequestURI("/api/chat");
        MockHttpServletResponse resp = new MockHttpServletResponse();
        boolean[] reached = {false};

        f.doFilter(req, resp, (r, s) -> reached[0] = true);

        assertTrue(reached[0], "拿不到长度也必须放行，不能因为探测不到就拒绝请求");
        assertEquals("1", resp.getHeader("X-Quota-Day-Used"));
        assertEquals(0, f.snapshot().tokens(), "长度未知 ⇒ 记 0 token，不记账面假数");
    }

    @Test
    @DisplayName("路径清单解析：多路径/空格/空串三种形态都按预期")
    void parsePathsHandlesForms() {
        assertEquals(Set.of("/api/chat"), QuotaFilter.parsePaths("/api/chat"));
        assertEquals(Set.of("/api/chat", "/api/emotion"), QuotaFilter.parsePaths(" /api/chat , /api/emotion "));
        assertTrue(QuotaFilter.parsePaths("").isEmpty(), "空串 = 一个都不计量（只留读数，不拦人）");
        assertTrue(QuotaFilter.parsePaths(null).isEmpty());
    }

    @Test
    @DisplayName("非 /api 路径根本不过滤（静态页不该被计量）")
    void skipsNonApi() {
        QuotaFilter f = filter(true, Set.of("/api/chat"), 1, 0);
        MockHttpServletRequest req = new MockHttpServletRequest("GET", "/index.html");
        req.setRequestURI("/index.html");
        assertTrue(f.shouldNotFilter(req));
        assertFalse(f.shouldNotFilter(post("/api/chat", "{}")));
    }

    @Test
    @DisplayName("Content-Length 非法时按 -1 处理，不抛异常把请求打死")
    void malformedLengthIsIgnored() {
        MockHttpServletRequest req = new MockHttpServletRequest("POST", "/api/chat");
        req.setRequestURI("/api/chat");
        req.addHeader("Content-Length", "not-a-number");
        assertEquals(-1L, QuotaFilter.declaredLength(req));
        assertEquals(0L, UsageLedger.estimateTokens(-1L));
    }
}
