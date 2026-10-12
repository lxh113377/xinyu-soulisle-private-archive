package com.xinyu.soulisle.config;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * r128：结构化访问日志的判据。
 *
 * <p>本类除行为断言外还承担一条**红线守卫**：逐行扫服务端源码，确认没有任何一处把
 * 请求体 / 响应体 / Authorization 写进日志。密钥零落盘是本仓第一红线，日志同样是落盘，
 * 「日志里打个 key」和「配置里写个 key」是同一个错误。
 */
class AccessLogFilterTest {

    private static MockHttpServletRequest get(String uri) {
        MockHttpServletRequest req = new MockHttpServletRequest("GET", uri);
        req.setRequestURI(uri);
        return req;
    }

    @Test
    @DisplayName("业务链跑完即计数一次，并带上最终状态")
    void countsAndSeesFinalStatus() throws Exception {
        AccessLogFilter f = new AccessLogFilter(true);
        MockHttpServletResponse resp = new MockHttpServletResponse();
        f.doFilter(get("/api/chat"), resp, (r, s) -> resp.setStatus(200));
        assertEquals(1L, f.count());
        assertEquals(0L, f.slowCount());
    }

    @Test
    @DisplayName("业务链抛异常时也要计数 —— finally 语义，崩了也留痕")
    void countsEvenWhenChainThrows() {
        AccessLogFilter f = new AccessLogFilter(true);
        try {
            f.doFilter(get("/api/chat"), new MockHttpServletResponse(), (r, s) -> {
                throw new IllegalStateException("boom");
            });
        } catch (Exception ignored) {
            // 预期抛出，断言的是计数
        }
        assertEquals(1L, f.count(), "异常路径也必须计数，否则崩了就是黑洞");
    }

    @Test
    @DisplayName("腿名归一：路径里的会话 id 不进日志，否则日志没法聚合")
    void legIsNormalized() {
        assertEquals("/api/memory", AccessLogFilter.leg("/api/memory/search"));
        assertEquals("/api/memory", AccessLogFilter.leg("/api/memory/abc123"));
        assertEquals("/api/chat", AccessLogFilter.leg("/api/chat"));
        assertEquals("unknown", AccessLogFilter.leg(null));
    }

    @Test
    @DisplayName("enabled=false 时仍计数但不写日志（计数是读数面，与日志开关解耦）")
    void disabledStillCounts() throws Exception {
        AccessLogFilter f = new AccessLogFilter(false);
        f.doFilter(get("/api/chat"), new MockHttpServletResponse(), (r, s) -> { });
        assertEquals(1L, f.count());
        assertEquals(0L, f.slowCount());
    }

    @Test
    @DisplayName("静态资源不经这道闸（避免首屏资源刷爆日志）")
    void staticPathsAreNotLogged() {
        AccessLogFilter f = new AccessLogFilter(true);
        assertTrue(f.shouldNotFilter(get("/index.html")), "静态页应被跳过");
        assertFalse(f.shouldNotFilter(get("/api/chat")), "API 腿不该被跳过");
    }

    @Test
    @DisplayName("红线：服务端源码里不得出现「把请求体/响应体/密钥写进日志」的写法")
    void sourceNeverLogsPayloadOrSecret() throws Exception {
        // 测试期工作目录是**项目根**（Maven 的 surefire 默认），不是 server/
        Path src = Path.of("server", "src", "main", "java", "com", "xinyu", "soulisle");
        assertTrue(Files.isDirectory(src), "源码目录不在预期位置，判据自身失效：" + src.toAbsolutePath());

        // 先把内容读出来再做行级判定：lambda 里抛 IOException 编不过（第一版就踩了这条）
        List<Path> javaFiles;
        try (Stream<Path> files = Files.walk(src)) {
            javaFiles = files.filter(p -> p.toString().endsWith(".java"))
                    .collect(Collectors.toList());
        }
        assertFalse(javaFiles.isEmpty(), "没扫到任何 .java，判据读数面为空（假通过形态）");

        List<String> offenders = new ArrayList<>();
        for (Path p : javaFiles) {
            String content = Files.readString(p, java.nio.charset.StandardCharsets.UTF_8);
            boolean hit = content.lines().anyMatch(AccessLogFilterTest::looksLikePayloadLogging);
            if (hit) {
                offenders.add(p.getFileName().toString());
            }
        }
        assertTrue(offenders.isEmpty(),
                "以下文件疑似把请求体或密钥送进日志（密钥零落盘红线）：" + offenders);
    }

    /** 只对「日志调用行」判红，避免把普通变量名 body 当成问题 */
    private static boolean looksLikePayloadLogging(String line) {
        String t = line.trim();
        boolean isLogCall = t.contains("LOGGER.") || t.contains("logger.") || t.contains("log.");
        if (!isLogCall) {
            return false;
        }
        String lower = t.toLowerCase();
        boolean carriesPayload = lower.contains("getcontentasstring")
                || lower.contains("requestbody")
                || lower.contains("authorization")
                || lower.contains("apikey")
                || lower.contains("llm.key")
                || lower.contains("this.key")
                || lower.contains("xinyu-token");
        return carriesPayload;
    }
}