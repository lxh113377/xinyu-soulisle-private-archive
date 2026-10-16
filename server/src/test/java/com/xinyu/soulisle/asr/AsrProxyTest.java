package com.xinyu.soulisle.asr;

import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * r187 补齐：AsrProxy 是 r177/184 落地的 ASR 服务端面，此前构建期 0 用例
 * （jacoco LINE 17.5%）—— 与 r77 立门时 LlmProxy 的欠债同型。
 *
 * <p>上游用 JDK 内置 HttpServer（回环 + 端口 0），沿用 LlmProxyTest 的脚本化桩模式：
 * 零新增依赖、零公网、零密钥。要测的就是「请求怎么拼、失败怎么折」这段真走 socket
 * 的逻辑：方言 URL 编码、vocab 只认 off、上游错误码透传、不可达降级口径
 * （红线：永不抛异常、永不返回占位文本）。
 */
class AsrProxyTest {

    private HttpServer stub;
    private String base;
    private final Deque<Scripted> scripts = new ArrayDeque<>();
    private final List<Observed> observed = new ArrayList<>();

    private record Scripted(int status, String contentType, byte[] body) {}

    private record Observed(String uri, String contentType, byte[] body) {}

    @BeforeEach
    void startStub() throws IOException {
        stub = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        stub.createContext("/transcribe", ex -> {
            observed.add(new Observed(ex.getRequestURI().toString(),
                    ex.getRequestHeaders().getFirst("Content-Type"),
                    readAll(ex.getRequestBody())));
            Scripted s = scripts.isEmpty()
                    ? new Scripted(200, "application/json",
                            utf8("{\"text\":\"兜底\",\"engine\":\"qwen\"}"))
                    : scripts.pop();
            ex.getResponseHeaders().set("Content-Type", s.contentType());
            ex.sendResponseHeaders(s.status(), s.body().length);
            ex.getResponseBody().write(s.body());
            ex.close();
        });
        stub.createContext("/health", ex -> {
            Scripted s = scripts.isEmpty()
                    ? new Scripted(200, "application/json", utf8("{\"ready\":true}"))
                    : scripts.pop();
            ex.getResponseHeaders().set("Content-Type", s.contentType());
            ex.sendResponseHeaders(s.status(), s.body().length);
            ex.getResponseBody().write(s.body());
            ex.close();
        });
        stub.start();
        base = "http://127.0.0.1:" + stub.getAddress().getPort();
    }

    @AfterEach
    void stopStub() {
        stub.stop(0);
    }

    private static byte[] utf8(String s) {
        return s.getBytes(StandardCharsets.UTF_8);
    }

    private static byte[] readAll(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        in.transferTo(out);
        return out.toByteArray();
    }

    private static int freePort() throws IOException {
        try (ServerSocket socket = new ServerSocket(0)) {
            socket.setReuseAddress(false);
            return socket.getLocalPort();
        }
    }

    private void script(int status, String body) {
        scripts.add(new Scripted(status, "application/json", utf8(body)));
    }

    @Test
    @DisplayName("成功腿：上游 200 ⇒ ok=true，text/engine/rtf 逐字段折回")
    void successFoldsFields() {
        AsrProxy p = new AsrProxy(base, 5000, true);
        script(200, "{\"text\":\"睡不着\",\"dialect\":\"mandarin\",\"engine\":\"qwen-asr\","
                + "\"inferMs\":120,\"rtf\":0.4}");
        AsrProxy.Result r = p.transcribe(utf8("wav"), "mandarin", null);
        assertTrue(r.ok());
        assertEquals("睡不着", r.text());
        assertEquals("mandarin", r.dialect());
        assertEquals("qwen-asr", r.engine());
        assertEquals(120L, r.inferMs());
        assertEquals(0.4, r.rtf());
        assertNull(r.err());
        assertEquals(1, observed.size());
        assertEquals("/transcribe?dialect=mandarin", observed.get(0).uri());
        assertEquals("audio/wav", observed.get(0).contentType());
    }

    @Test
    @DisplayName("vocab=off 才透传；其他值（含自定义串）一律不进查询串")
    void vocabOnlyOffPassesThrough() {
        AsrProxy p = new AsrProxy(base, 5000, true);
        script(200, "{\"text\":\"x\"}");
        p.transcribe(utf8("wav"), "mandarin", "off");
        assertEquals("/transcribe?dialect=mandarin&vocab=off", observed.get(0).uri());
        script(200, "{\"text\":\"x\"}");
        p.transcribe(utf8("wav"), "mandarin", "任意的自定义词表");
        assertEquals("/transcribe?dialect=mandarin", observed.get(1).uri());
        script(200, "{\"text\":\"x\"}");
        p.transcribe(utf8("wav"), "mandarin", null);
        assertEquals("/transcribe?dialect=mandarin", observed.get(2).uri());
    }

    @Test
    @DisplayName("上游 503 带 JSON error ⇒ 透传该错误码（前端据此分流回落）")
    void upstreamErrorCodePassesThrough() {
        AsrProxy p = new AsrProxy(base, 5000, true);
        script(503, "{\"error\":\"asr-unavailable\"}");
        AsrProxy.Result r = p.transcribe(utf8("wav"), "mandarin", null);
        assertFalse(r.ok());
        assertEquals("asr-unavailable", r.err());
        assertEquals("", r.text());
    }

    @Test
    @DisplayName("上游非 2xx 且 body 非 JSON ⇒ 错误码退成 upstream-<status>")
    void upstreamNonJsonErrorBecomesStatus() {
        AsrProxy p = new AsrProxy(base, 5000, true);
        scripts.add(new Scripted(500, "text/plain", utf8("oops")));
        AsrProxy.Result r = p.transcribe(utf8("wav"), "mandarin", null);
        assertFalse(r.ok());
        assertEquals("upstream-500", r.err());
    }

    @Test
    @DisplayName("enabled=false ⇒ 探针与转写都不发请求（C15 零探测红线）")
    void disabledNeverCallsUpstream() {
        AsrProxy p = new AsrProxy(base, 5000, false);
        assertFalse(p.enabled());
        assertFalse(p.ready());
        AsrProxy.Result r = p.transcribe(utf8("wav"), "mandarin", null);
        assertFalse(r.ok());
        assertEquals("asr-disabled", r.err());
        assertTrue(observed.isEmpty(), "默认态一条请求都不许发");
    }

    @Test
    @DisplayName("空音频 ⇒ empty-audio，不达上游")
    void emptyAudioRejected() {
        AsrProxy p = new AsrProxy(base, 5000, true);
        AsrProxy.Result r = p.transcribe(new byte[0], "mandarin", null);
        assertFalse(r.ok());
        assertEquals("empty-audio", r.err());
        assertTrue(observed.isEmpty());
    }

    @Test
    @DisplayName("服务不可达（没人监听的端口）⇒ asr-unavailable，永不抛异常")
    void unreachableDegradesNotThrows() throws IOException {
        AsrProxy p = new AsrProxy("http://127.0.0.1:" + freePort(), 2000, true);
        AsrProxy.Result r = p.transcribe(utf8("wav"), "mandarin", null);
        assertFalse(r.ok());
        assertEquals("asr-unavailable", r.err());
        assertFalse(p.ready());
    }

    @Test
    @DisplayName("ready()：/health 回 ready=true 才算就绪；非 2xx / ready=false 都算不就绪")
    void readyProbeSemantics() {
        AsrProxy p = new AsrProxy(base, 5000, true);
        script(200, "{\"ready\":true}");
        assertTrue(p.ready());
        script(200, "{\"ready\":false}");
        assertFalse(p.ready());
        script(404, "{}");
        assertFalse(p.ready());
    }

    @Test
    @DisplayName("构造器边界：blank URL 不抛、尾斜杠剥掉后仍可用、非正超时不抛")
    void constructorDefaults() {
        AsrProxy a = new AsrProxy("  ", 1000, true);   // 默认端口没桩 ⇒ 只验构造不抛 + 走到降级
        AsrProxy.Result ra = a.transcribe(utf8("w"), "mandarin", null);
        assertFalse(ra.ok());
        assertEquals("asr-unavailable", ra.err());
        AsrProxy b = new AsrProxy(base + "/", 0, true);
        script(200, "{\"text\":\"x\"}");
        AsrProxy.Result rb = b.transcribe(utf8("w"), "mandarin", null);
        assertTrue(rb.ok());
        assertEquals("/transcribe?dialect=mandarin", observed.get(observed.size() - 1).uri());
    }

    @Test
    @DisplayName("方言为空白 ⇒ 回落 mandarin（脏值不透传给引擎）")
    void blankDialectFallsBackToMandarin() {
        AsrProxy p = new AsrProxy(base, 5000, true);
        script(200, "{\"text\":\"x\"}");
        p.transcribe(utf8("wav"), "  ", null);
        assertEquals("/transcribe?dialect=mandarin", observed.get(0).uri());
    }
}
