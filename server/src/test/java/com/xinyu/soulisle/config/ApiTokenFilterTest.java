package com.xinyu.soulisle.config;

import jakarta.servlet.FilterChain;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

/**
 * 可选鉴权过滤器边界守卫（r76；对应 AC-OBS-12，此前只由 curl 带外验过，构建期 0 用例）。
 *
 * <p>三条边界都不许反：
 * ① token 留空 = 完全放行（演示形态，v1/J1-J4 行为不变）；
 * ② token 非空时 <b>只有</b> /api/** 被护，{@code /api/health} 与静态页永远放行
 *    —— 探针和负载均衡一旦因鉴权失败，会把「活着的服务」判成死的；
 * ③ 缺失头与错误头都必须 401，不得因「头没带」被读成「带了个空 token 恰好匹配」。
 */
class ApiTokenFilterTest {

    private static MockHttpServletRequest req(String uri, String token) {
        MockHttpServletRequest r = new MockHttpServletRequest("GET", uri);
        r.setRequestURI(uri);
        if (token != null) {
            r.addHeader("X-Xinyu-Token", token);
        }
        return r;
    }

    @Test
    @DisplayName("token 留空 ⇒ 全部接口放行，一个 401 都不产生")
    void emptyTokenPassesEverything() throws Exception {
        ApiTokenFilter f = new ApiTokenFilter("");
        FilterChain chain = mock(FilterChain.class);
        MockHttpServletResponse resp = new MockHttpServletResponse();
        f.doFilter(req("/api/memory/stats", null), resp, chain);
        verify(chain).doFilter(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
        assertEquals(200, resp.getStatus());

        FilterChain chain2 = mock(FilterChain.class);
        f.doFilter(req("/api/chat", "wrong-token-anyway"), new MockHttpServletResponse(), chain2);
        verify(chain2).doFilter(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
    }

    @Test
    @DisplayName("token 非空 ⇒ 无头 401、错头 401、对头放行；401 体是固定 JSON 且 UTF-8")
    void guardedTokenBehavior() throws Exception {
        ApiTokenFilter f = new ApiTokenFilter("s3cret");

        MockHttpServletResponse noHeader = new MockHttpServletResponse();
        FilterChain c1 = mock(FilterChain.class);
        f.doFilter(req("/api/memory/stats", null), noHeader, c1);
        assertEquals(401, noHeader.getStatus());
        verify(c1, never()).doFilter(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
        assertEquals("{\"error\":\"unauthorized\"}", noHeader.getContentAsString());
        assertTrue(noHeader.getCharacterEncoding().equalsIgnoreCase("UTF-8"));

        MockHttpServletResponse wrong = new MockHttpServletResponse();
        f.doFilter(req("/api/emotion", "nope"), wrong, mock(FilterChain.class));
        assertEquals(401, wrong.getStatus());

        FilterChain ok = mock(FilterChain.class);
        f.doFilter(req("/api/memory/stats", "s3cret"), new MockHttpServletResponse(), ok);
        verify(ok).doFilter(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
    }

    @Test
    @DisplayName("开鉴权后 /api/health 与静态页仍永远放行 —— 探针不该被自家门禁拦死")
    void healthAndStaticAlwaysOpen() throws Exception {
        ApiTokenFilter f = new ApiTokenFilter("s3cret");

        FilterChain health = mock(FilterChain.class);
        MockHttpServletResponse resp = new MockHttpServletResponse();
        f.doFilter(req("/api/health", null), resp, health);
        verify(health).doFilter(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
        assertEquals(200, resp.getStatus());

        FilterChain page = mock(FilterChain.class);
        f.doFilter(req("/index.html", null), new MockHttpServletResponse(), page);
        verify(page).doFilter(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());

        // 前缀边界：/api 不带斜杠、/apifoo 都不该被 startsWith("/api/") 误伤
        FilterChain edge = mock(FilterChain.class);
        f.doFilter(req("/apifoo", null), new MockHttpServletResponse(), edge);
        verify(edge).doFilter(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
    }

    @Test
    @DisplayName("null token 与纯空白 token 都按留空处理：该关时关严，该开时不许半开")
    void nullAndBlankTokenAreOpen() throws Exception {
        for (String raw : new String[] {null, "   "}) {
            FilterChain chain = mock(FilterChain.class);
            new ApiTokenFilter(raw).doFilter(req("/api/memory/stats", null), new MockHttpServletResponse(), chain);
            verify(chain).doFilter(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
        }
        // 对照组：非空 token 时同一「无头」请求必须 401，证明上面两格走的是放行分支而非判据失效
        ApiTokenFilter armed = new ApiTokenFilter(" s3cret ");
        MockHttpServletResponse resp = new MockHttpServletResponse();
        armed.doFilter(req("/api/memory/stats", null), resp, mock(FilterChain.class));
        assertEquals(401, resp.getStatus(), "token 两侧空白必须被 trim，否则配了密钥却形同没配");
    }
}
