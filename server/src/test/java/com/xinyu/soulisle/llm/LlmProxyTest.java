package com.xinyu.soulisle.llm;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
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
import java.time.Duration;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * r77：{@link LlmProxy} 的上游侧行为此前只有带外 curl 验过、构建期 0 用例（覆盖率 LINE 40% 时代遗留）。
 *
 * <p>上游用 JDK 内置 {@link HttpServer}（回环 + 端口 0）替掉，而不是 Mockito 打桩 HttpClient：
 * 要测的就是「请求怎么拼、响应怎么折」这段真走 socket 的逻辑，把 socket 桩掉等于把被测对象换掉。
 * 零新增依赖、零公网出口、零密钥（key 全是假串）。
 */
class LlmProxyTest {

    private static final ObjectMapper M = new ObjectMapper();

    private HttpServer stub;
    private String base;
    private final Deque<Scripted> scripts = new ArrayDeque<>();
    private final List<ObservedRequest> observed = new ArrayList<>();

    private record Scripted(int status, String contentType, byte[] body) {}

    private record ObservedRequest(String uri, String authorization, String body) {}

    @BeforeEach
    void startStub() throws IOException {
        stub = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        stub.createContext("/v1/chat/completions", ex -> {
            String raw = readAll(ex.getRequestBody());
            observed.add(new ObservedRequest(ex.getRequestURI().toString(),
                    ex.getRequestHeaders().getFirst("Authorization"), raw));
            Scripted s = scripts.isEmpty() ? new Scripted(200, "application/json",
                    "{\"choices\":[{\"message\":{\"content\":\"兜底\"}}]}".getBytes(StandardCharsets.UTF_8)) : scripts.pop();
            if (s.body().length > 0) {
                ex.getResponseHeaders().set("Content-Type", s.contentType());
                ex.sendResponseHeaders(s.status(), s.body().length);
                ex.getResponseBody().write(s.body());
            } else {
                if (s.contentType() != null) {
                    ex.getResponseHeaders().set("Content-Type", s.contentType());
                }
                ex.sendResponseHeaders(s.status(), -1);
            }
            ex.close();
        });
        stub.start();
        base = "http://127.0.0.1:" + stub.getAddress().getPort() + "/v1";
    }

    @AfterEach
    void stopStub() {
        stub.stop(0);
    }

    private static String readAll(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        in.transferTo(out);
        return out.toString(StandardCharsets.UTF_8);
    }

    private static byte[] utf8(String s) {
        return s.getBytes(StandardCharsets.UTF_8);
    }

    /** 一个没人监听的端口：拿完即关，用来确定性地触发连接层异常那条腿 */
    private static int freePort() throws IOException {
        try (ServerSocket socket = new ServerSocket(0)) {
            socket.setReuseAddress(false);
            return socket.getLocalPort();
        }
    }

    private void script(int status, String contentType, String body) {
        scripts.add(new Scripted(status, contentType, utf8(body)));
    }

    private JsonNode msgs(String... roleAndContentPairs) throws Exception {
        var arr = M.createArrayNode();
        for (int i = 0; i < roleAndContentPairs.length; i += 2) {
            var o = arr.addObject();
            if (roleAndContentPairs[i] != null) {
                o.put("role", roleAndContentPairs[i]);
            }
            if (roleAndContentPairs[i + 1] != null) {
                o.put("content", roleAndContentPairs[i + 1]);
            }
        }
        return arr;
    }

    private JsonNode upstreamPayloadOf(int index) throws Exception {
        return M.readTree(observed.get(index).body());
    }

    @Test
    @DisplayName("密钥：null 与纯空白都算「没有 key」，带空白的要 trim 后上行；两参构造器仍可用")
    void keyNormalization() throws Exception {
        assertFalse(new LlmProxy(base, "m", null).hasKey(), "null key 不得判成有 key");
        assertFalse(new LlmProxy(base, "m", "   ").hasKey(), "纯空白 trim 后必须为空");
        assertTrue(new LlmProxy(base, "m", "sk-fake").hasKey());

        new LlmProxy(base, "m", "  sk-fake  ", 5).call(msgs("user", "你好"), null, null);
        assertEquals("Bearer sk-fake", observed.get(0).authorization(), "上行头必须是 trim 后的 Bearer");
    }

    @Test
    @DisplayName("上行请求体逐字段对齐 v1 契约：缺省 temperature 0.85 / max_tokens 220，显式给值则照给")
    void payloadDefaultsAndOverrides() throws Exception {
        script(200, "application/json", "{\"ok\":true}");
        LlmProxy p = new LlmProxy(base, "deepseek-chat", "sk-fake", 5);

        LlmProxy.Result r = p.call(msgs("user", "今天天气不错"), null, null);
        assertEquals(200, r.status());
        assertEquals("{\"ok\":true}", r.body(), "2xx JSON 响应体必须逐字透传，不重排");
        JsonNode sent = upstreamPayloadOf(0);
        assertEquals("deepseek-chat", sent.get("model").asText());
        assertEquals(0.85, sent.get("temperature").asDouble(), 1e-9);
        assertEquals(220, sent.get("max_tokens").asInt());
        assertFalse(sent.has("stream"), "非流式不得带 stream 字段");
        assertEquals("/v1/chat/completions", observed.get(0).uri());

        p.call(msgs("user", "x"), 0.3, 64);
        JsonNode sent2 = upstreamPayloadOf(1);
        assertEquals(0.3, sent2.get("temperature").asDouble(), 1e-9);
        assertEquals(64, sent2.get("max_tokens").asInt());
    }

    @Test
    @DisplayName("base 结尾多一个斜杠不会拼出双斜杠路径（两参构造器走默认 10s 建连）")
    void baseTrailingSlashNormalized() throws Exception {
        script(200, "application/json", "{}");
        new LlmProxy(base + "/", "m", "sk-fake").call(msgs("user", "x"), null, null);
        assertEquals("/v1/chat/completions", observed.get(0).uri());
    }

    @Test
    @DisplayName("messages 非法一律折成空数组：null / 非数组 / 数组里的非对象 / 缺 role 或 content 的对象")
    void malformedMessagesCollapseToEmptyList() throws Exception {
        LlmProxy p = new LlmProxy(base, "m", "sk-fake", 5);
        script(200, "application/json", "{}");
        script(200, "application/json", "{}");
        script(200, "application/json", "{}");

        p.call(null, null, null);
        assertTrue(upstreamPayloadOf(0).get("messages").isEmpty(), "messages=null 必须按空数组处理（v1 行为）");

        p.call(M.readTree("\"只是字符串\""), null, null);
        assertTrue(upstreamPayloadOf(1).get("messages").isEmpty(), "非数组必须按空数组处理");

        JsonNode mixed = M.readTree("[\"裸字符串\",{\"role\":\"user\"},{\"content\":\"只有内容\"},7]");
        p.call(mixed, null, null);
        JsonNode out = upstreamPayloadOf(2).get("messages");
        assertEquals(2, out.size(), "非对象元素丢掉，对象元素保留");
        assertFalse(out.get(0).has("content"), "缺 content 不得凭空造字段");
        assertFalse(out.get(1).has("role"), "缺 role 不得凭空造字段");
        assertEquals("只有内容", out.get(1).get("content").asText());
    }

    @Test
    @DisplayName("上游空响应体与非 JSON 响应体都折成 upstream-nonjson（状态码仍原样透传）")
    void upstreamBodyFallbacks() throws Exception {
        LlmProxy p = new LlmProxy(base, "m", "sk-fake", 5);

        scripts.add(new Scripted(200, null, new byte[0]));
        LlmProxy.Result empty = p.call(msgs("user", "x"), null, null);
        assertEquals(200, empty.status());
        assertEquals("{\"error\":\"upstream-nonjson\"}", empty.body());

        script(503, "text/html", "<html>proxy blew up</html>");
        LlmProxy.Result html = p.call(msgs("user", "x"), null, null);
        assertEquals(503, html.status(), "上游状态码不得被改写");
        assertEquals("{\"error\":\"upstream-nonjson\"}", html.body());
    }

    @Test
    @DisplayName("连接层异常（没人监听）折成 502 upstream-error，且不挂到请求超时之外")
    void connectionFailureMapsToBadGateway() throws Exception {
        int dead = freePort();
        LlmProxy p = new LlmProxy("http://127.0.0.1:" + dead + "/v1", "m", "sk-fake", 2);
        long t0 = System.nanoTime();
        LlmProxy.Result r = p.call(msgs("user", "x"), null, null, Duration.ofSeconds(5));
        long ms = (System.nanoTime() - t0) / 1_000_000;
        assertEquals(502, r.status());
        assertEquals("{\"error\":\"upstream-error\"}", r.body());
        assertTrue(ms < 5000, "连接被拒应立刻返回，实测 " + ms + "ms");
    }

    @Test
    @DisplayName("stream=true 且上游真是 SSE → 逐块直通，内容一字节不差；请求体带 stream:true")
    void sseStreamPassesThrough() throws Exception {
        script(200, "text/event-stream", "data: {\"c\":1}\n\ndata: [DONE]\n\n");
        LlmProxy.StreamResult s = new LlmProxy(base, "m", "sk-fake", 5)
                .openStream(msgs("user", "x"), null, null);

        assertEquals(200, s.status());
        assertTrue(s.isEventStream());
        assertEquals("text/event-stream", s.contentType().split(";")[0]);
        try (InputStream in = s.bodyStream()) {
            assertArrayEquals(utf8("data: {\"c\":1}\n\ndata: [DONE]\n\n"), in.readAllBytes());
        }
        assertTrue(upstreamPayloadOf(0).path("stream").asBoolean(), "流式上行必须带 stream:true");
    }

    @Test
    @DisplayName("流式回落三形：2xx 但非 SSE / 非 2xx 但挂着 SSE / 空体与非 JSON，全部折回整包 JSON")
    void streamFallbackShapes() throws Exception {
        LlmProxy p = new LlmProxy(base, "m", "sk-fake", 5);

        script(200, "application/json", "{\"error\":\"rate_limited\"}");
        LlmProxy.StreamResult notSse = p.openStream(msgs("user", "x"), null, null);
        assertFalse(notSse.isEventStream());
        assertEquals("{\"error\":\"rate_limited\"}", notSse.body(), "上游报错体要原样交给控制器回给前端");

        script(500, "text/event-stream", "{\"error\":\"boom\"}");
        LlmProxy.StreamResult badStatus = p.openStream(msgs("user", "x"), null, null);
        assertFalse(badStatus.isEventStream(), "非 200 即使 content-type 是 SSE 也不直通");
        assertEquals(500, badStatus.status());
        assertEquals("{\"error\":\"boom\"}", badStatus.body());

        scripts.add(new Scripted(204, null, new byte[0]));
        LlmProxy.StreamResult empty = p.openStream(msgs("user", "x"), null, null);
        assertFalse(empty.isEventStream());
        assertEquals("{\"error\":\"upstream-nonjson\"}", empty.body());

        script(200, "text/plain", "not json at all");
        LlmProxy.StreamResult htmlish = p.openStream(msgs("user", "x"), null, null);
        assertFalse(htmlish.isEventStream());
        assertEquals("{\"error\":\"upstream-nonjson\"}", htmlish.body());
    }

    @Test
    @DisplayName("流式分支的连接层异常同样折成 502 整包（不产生半开流）")
    void streamConnectionFailure() throws Exception {
        int dead = freePort();
        LlmProxy.StreamResult s = new LlmProxy("http://127.0.0.1:" + dead + "/v1", "m", "sk-fake", 2)
                .openStream(msgs("user", "x"), null, null);
        assertFalse(s.isEventStream());
        assertEquals(502, s.status());
        assertEquals("{\"error\":\"upstream-error\"}", s.body());
    }

    /**
     * r82（建议8 的归因落地）：T8 点名的 {@code LlmProxy.call}(漏 6 指令) / {@code openStream}(漏 8 指令)
     * 逐行复算后全部落在同两支上 —— {@code LlmProxy.java:95} 与 {@code :126} 的 {@code payload == null}
     * → {@code bad-json}，而它们唯一的来源是 {@code :166-167} 的 {@code writeValueAsString} catch。
     *
     * <p>{@code toMessageList} 把每个入参形状都归一成 {@code Map<String, String>}（非对象跳过、
     * {@code hasNonNull} 挡掉 null、其余一律 {@code asText()}），所以那个 catch **结构上不可能被触发**。
     * 沿用 r77 的原则：不为凑覆盖率写反射。
     *
     * <p>但这条不变量此前只有散文在说，没有东西钉着 —— 本用例就是那颗钉：拿四类畸形入参走两条公开出口，
     * 断言上行的每条消息字段都是字符串、且状态码仍是上游的而不是 500。下一次有人让 {@code toMessageList}
     * 漏掉某种归一（比如原样塞回 JsonNode），这条会当场红，而不是等下一个人重新做一遍不可达性归因。
     */
    @Test
    @DisplayName("畸形 messages 一律归一成字符串：bad-json 那两支是结构不可达，用它做不变量而非反射")
    void hostileMessagesNormalizeInsteadOfCollapsingToBadJson() throws Exception {
        var arr = M.createArrayNode();
        arr.add("裸字符串不是对象");
        var weird = arr.addObject();
        weird.putPOJO("role", new int[] {1, 2});
        weird.putArray("content").add("a").add("b");
        var hollow = arr.addObject();
        hollow.put("name", "小屿");
        var nulled = arr.addObject();
        nulled.putNull("role");
        nulled.put("content", "在的");

        LlmProxy p = new LlmProxy(base, "m", "sk-fake", 5);

        script(200, "application/json", "{\"choices\":[{\"message\":{\"content\":\"好\"}}]}");
        LlmProxy.Result r = p.call(arr, null, null);
        assertEquals(200, r.status(), "若走了 bad-json 那支会是 500，这里必须仍是上游状态码");
        JsonNode sent = upstreamPayloadOf(0).path("messages");
        assertTrue(sent.isArray(), "上行必须仍是 messages 数组");
        assertEquals(3, sent.size(), "非对象元素应被跳过，对象即使畸形也要留下");
        for (JsonNode m : sent) {
            for (String field : new String[] {"role", "content"}) {
                if (m.has(field)) {
                    assertTrue(m.get(field).isTextual(),
                            field + " 必须已被 asText() 归一成字符串，实为 " + m.get(field));
                }
            }
        }
        assertTrue(sent.get(2).hasNonNull("content"), "putNull(role) 只该丢掉 role，不该连 content 一起丢");

        script(200, "application/json", "{\"choices\":[{\"message\":{\"content\":\"好\"}}]}");
        LlmProxy.StreamResult s = p.openStream(arr, null, null);
        assertEquals(200, s.status(), "流式腿同样不得走 bad-json");
    }

    @Test
    @DisplayName("r83 不可达腿留证：上游零字节响应经 BodyHandlers.ofString 到手是空串而非 null")
    void emptyUpstreamBodyArrivesAsBlankNotNull() throws Exception {
        // LlmProxy 里 `body == null` 那一支常年报 missed。这里不打桩、走真 socket 复现同一条 JDK 承诺：
        // 零字节响应体读出来必须是空串。哪天这条先红，那一支就不再是死代码，归类要跟着改。
        // 桩脚本是**队列**：一次请求消费一条。裸探针和 p.call 各要一条空体，
        // 只 script 一条时第二条请求会掉进桩的默认响应（本轮第一次就是这么被测出「兜底」的）。
        script(200, "application/json", "");
        script(200, "application/json", "");
        java.net.http.HttpClient client = java.net.http.HttpClient.newHttpClient();
        java.net.http.HttpRequest req = java.net.http.HttpRequest
                .newBuilder(java.net.URI.create(base + "/chat/completions"))
                .POST(java.net.http.HttpRequest.BodyPublishers.ofString("{}", StandardCharsets.UTF_8))
                .build();
        java.net.http.HttpResponse<String> raw = client.send(req,
                java.net.http.HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        org.junit.jupiter.api.Assertions.assertNotNull(raw.body(),
                "ofString 不得返回 null，否则 LlmProxy 的 body==null 那一支是活的");
        assertTrue(raw.body().isEmpty(), "零字节响应体应是空串，实得长度=" + raw.body().length());

        LlmProxy p = new LlmProxy(base, "m", "sk-fake", 5);
        LlmProxy.Result folded = p.call(msgs("user", "x"), null, null);
        assertEquals(200, folded.status(), "折成 upstream-nonjson 时状态码仍归上游");
        assertEquals("{\"error\":\"upstream-nonjson\"}", folded.body());
    }
}
