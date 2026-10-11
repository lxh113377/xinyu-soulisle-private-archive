package com.xinyu.soulisle.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import com.xinyu.soulisle.engine.EmotionClassifier;
import com.xinyu.soulisle.engine.ModelProxy;
import com.xinyu.soulisle.llm.LlmProxy;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.ResponseEntity;

import java.io.IOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * 本地模型腿的**行为回执**（r121 改造三）。
 *
 * <p>动因不是「覆盖率数字好看」：{@code _test/java_test_guard.py} 的 T8 长期点名
 * {@code EmotionController.modelVerdictJson(未触达)}——也就是「接口会比 LLM 腿多输出一个
 * confidence」这句话，从写下来到本轮**一次都没被执行过**。本仓把这类形态记为
 * 「存在性不等于行为」（决策 #1 的「可单测」曾长期是能力声称而非产物，同一族）。
 *
 * <p>上游用 JDK 内置 {@link HttpServer}（回环 + 端口 0）替掉：零新依赖、零公网、零密钥，
 * 与 {@code LlmProxyTest} / {@code ModelProxyTest} 同一套桩法。
 */
class EmotionControllerModelRouteTest {

    private static final ObjectMapper M = new ObjectMapper();

    private HttpServer stub;
    private String url;
    private volatile int status = 200;
    private volatile String body = "{\"emotion\":\"sadness\",\"intensity\":0.72,\"confidence\":0.83}";

    @BeforeEach
    void startStub() throws IOException {
        stub = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        stub.createContext("/classify", ex -> {
            byte[] out = body.getBytes(StandardCharsets.UTF_8);
            ex.getResponseHeaders().add("Content-Type", "application/json");
            ex.sendResponseHeaders(status, out.length);
            ex.getResponseBody().write(out);
            ex.close();
        });
        stub.start();
        url = "http://127.0.0.1:" + stub.getAddress().getPort();
    }

    @AfterEach
    void stopStub() {
        if (stub != null) {
            stub.stop(0);
        }
    }

    private EmotionController controller(String route) {
        LlmProxy llm = mock(LlmProxy.class);
        when(llm.hasKey()).thenReturn(false);
        return new EmotionController(
                new EmotionClassifier(llm, new ModelProxy(url, 1500), 8000L, route),
                "./_test/emotion-eval-dataset.json");
    }

    /** 控制器收的是**原始 JSON 串**（emotion(String raw)），不是 JsonNode；用 Jackson 造串，
     *  避免中文字面量里再嵌一层转义引号（本仓在册的「写文件会吞字面量内部引号」一族）。 */
    private String rawJson(String text) throws IOException {
        return M.writeValueAsString(M.createObjectNode().put("text", text));
    }

    private JsonNode post(String text) throws Exception {
        ResponseEntity<byte[]> r = controller("auto").emotion(rawJson(text));
        assertEquals(200, r.getStatusCode().value(), "端点本身必须 200，否则后面的断言都是空谈");
        return M.readTree(new String(r.getBody(), StandardCharsets.UTF_8));
    }

    @Test
    @DisplayName("模型腿接通时，响应的 model 必须带 confidence——这是它与 LLM 腿唯一的结构差")
    void modelVerdictCarriesConfidence() throws Exception {
        JsonNode node = post("心里堵得慌，说不上来的难受").path("model");
        assertTrue(node.isObject(), "model 应为对象；实际=" + node + "（未触达即本用例要抓的缺陷）");
        assertEquals("sadness", node.path("emotion").asText());
        assertEquals(0.83, node.path("confidence").asDouble(), 1e-9,
                "confidence 必须由模型腿原样带上（softmax top-1），前端证据标签读的就是它");
        assertEquals(0.72, node.path("intensity").asDouble(), 1e-9);
    }

    @Test
    @DisplayName("路由必须是模型腿而非词典腿：path 里要点名本地模型，否则 confidence 是无源之水")
    void routeIsAttributableToModelLeg() throws Exception {
        JsonNode root = post("心里堵得慌，说不上来的难受");
        assertTrue(root.path("path").asText().contains("模型"),
                "path 必须能看出这一路经过了本地模型；实际=" + root.path("path").asText());
    }

    @Test
    @DisplayName("反例两形：模型腿坏响应 / route=lexicon 时 model 一律为 null——上一条断言才有区分力")
    void modelLegAbsenceIsNotSilentlyFilled() throws Exception {
        status = 500;
        JsonNode broken = post("心里堵得慌，说不上来的难受").path("model");
        assertTrue(broken.isNull() || broken.isMissingNode(),
                "模型腿 5xx 却仍给出 model 判定 = 造出来读数；实际=" + broken);

        status = 200;
        LlmProxy llm = mock(LlmProxy.class);
        when(llm.hasKey()).thenReturn(false);
        EmotionController lexOnly = new EmotionController(
                new EmotionClassifier(llm, new ModelProxy(url, 1500), 8000L, "lexicon"),
                "./_test/emotion-eval-dataset.json");
        ResponseEntity<byte[]> r = lexOnly.emotion(rawJson("心里堵得慌"));
        JsonNode m2 = M.readTree(new String(r.getBody(), StandardCharsets.UTF_8)).path("model");
        assertTrue(m2.isNull() || m2.isMissingNode(),
                "route=lexicon 却出现 model 判定 ⇒ 开关没生效；实际=" + m2);
        assertNotNull(M.readTree(new String(r.getBody(), StandardCharsets.UTF_8)).path("lex"));
        assertFalse(r.getStatusCode().isError(), "关模型腿不应改变 HTTP 结论");
    }
}
