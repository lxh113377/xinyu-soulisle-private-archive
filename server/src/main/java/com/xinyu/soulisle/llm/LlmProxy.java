package com.xinyu.soulisle.llm;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.Map;

/**
 * 上游大模型代理：把 v1 的 Cloudflare Pages Function（deploy/functions/api/chat.js）1:1 搬到 Java 侧。
 *
 * <p>契约铁律（J2）：请求字段、上游请求拼装、错误码与错误体**必须与 v1 完全一致**，
 * 否则前端就不是「换 baseURL」而是「改代码」。密钥只从环境变量来，零落盘、零入库。
 */
@Component
public class LlmProxy {

    /** 上游调用结果：状态码 + 原始响应体（透传，不做任何重排，避免与前端解析口径漂移） */
    public record Result(int status, String body) {}

    /**
     * 流式调用结果：上游真是 SSE（2xx + text/event-stream）时带 bodyStream，由控制器逐块抄给前端；
     * 否则 stream 为 null、body 已备好（错误体与非流式响应走同一条回落路径）。
     */
    public record StreamResult(int status, String contentType, java.io.InputStream bodyStream, String body) {
        public boolean isEventStream() {
            return bodyStream != null;
        }
    }

    private static final double DEFAULT_TEMPERATURE = 0.85;
    private static final int DEFAULT_MAX_TOKENS = 220;

    private final ObjectMapper mapper = new ObjectMapper();
    private final HttpClient http;
    private final String base;
    private final String model;
    private final String key;

    public LlmProxy(@Value("${xinyu.llm.base}") String base,
                    @Value("${xinyu.llm.model}") String model,
                    @Value("${xinyu.llm.key:}") String key) {
        this.base = base;
        this.model = model;
        this.key = key == null ? "" : key.trim();
        this.http = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .build();
    }

    public boolean hasKey() {
        return !this.key.isEmpty();
    }

    /**
     * @param messages    对话消息数组（v1 行为：缺失或非法时按空数组处理）
     * @param temperature 缺失时 0.85（与 v1 `payload.temperature ?? 0.85` 一致）
     * @param maxTokens   缺失时 220（与 v1 `payload.max_tokens ?? 220` 一致）
     */
    public Result call(JsonNode messages, Double temperature, Integer maxTokens) {
        String payload = buildPayload(messages, temperature, maxTokens, false);
        if (payload == null) {
            return new Result(500, "{\"error\":\"bad-json\"}");
        }
        HttpRequest req = newRequest(payload);

        try {
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString(
                    java.nio.charset.StandardCharsets.UTF_8));
            String body = resp.body();
            if (body == null || body.isBlank()) {
                return new Result(resp.statusCode(), "{\"error\":\"upstream-nonjson\"}");
            }
            // 与 v1 Pages Function 对齐：上游非 JSON 体一律折成 upstream-nonjson（同状态码透传），
            // 否则前端会把 HTML 错误页当 OpenAI 响应解析。
            try {
                mapper.readTree(body);
            } catch (Exception parseFail) {
                return new Result(resp.statusCode(), "{\"error\":\"upstream-nonjson\"}");
            }
            return new Result(resp.statusCode(), body);
        } catch (Exception e) {
            return new Result(502, "{\"error\":\"upstream-error\"}");
        }
    }

    /**
     * 流式调用（SSE）。判定与 Pages Function 完全一致：只有「2xx + content-type 含 text/event-stream」
     * 才直通，其余一律折成整包 JSON 交给控制器按非流式回，前端据响应头自动回落（不产生半成品气泡）。
     */
    public StreamResult openStream(JsonNode messages, Double temperature, Integer maxTokens) {
        String payload = buildPayload(messages, temperature, maxTokens, true);
        if (payload == null) {
            return new StreamResult(500, null, null, "{\"error\":\"bad-json\"}");
        }
        HttpRequest req = newRequest(payload);
        try {
            HttpResponse<java.io.InputStream> resp = http.send(req, HttpResponse.BodyHandlers.ofInputStream());
            String ct = resp.headers().firstValue("content-type").orElse("");
            int status = resp.statusCode();
            if (status == 200 && ct.contains("text/event-stream")) {
                return new StreamResult(200, ct, resp.body(), null);
            }
            String body;
            try (java.io.InputStream in = resp.body()) {
                body = new String(in.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
            }
            if (body.isBlank()) {
                return new StreamResult(status, null, null, "{\"error\":\"upstream-nonjson\"}");
            }
            try {
                mapper.readTree(body);
            } catch (Exception parseFail) {
                return new StreamResult(status, null, null, "{\"error\":\"upstream-nonjson\"}");
            }
            return new StreamResult(status, null, null, body);
        } catch (Exception e) {
            return new StreamResult(502, null, null, "{\"error\":\"upstream-error\"}");
        }
    }

    /** 上游请求体：非流式与流式共用同一拼装，避免两条路径字段漂移 */
    private String buildPayload(JsonNode messages, Double temperature, Integer maxTokens, boolean stream) {
        Map<String, Object> upstreamBody = new java.util.LinkedHashMap<>();
        upstreamBody.put("model", model);
        upstreamBody.put("messages", toMessageList(messages));
        upstreamBody.put("temperature", temperature == null ? DEFAULT_TEMPERATURE : temperature);
        upstreamBody.put("max_tokens", maxTokens == null ? DEFAULT_MAX_TOKENS : maxTokens);
        if (stream) {
            upstreamBody.put("stream", true);
        }
        try {
            return mapper.writeValueAsString(upstreamBody);
        } catch (Exception e) {
            return null;
        }
    }

    private HttpRequest newRequest(String payload) {
        String url = base.replaceAll("/$", "") + "/chat/completions";
        return HttpRequest.newBuilder(URI.create(url))
                .timeout(Duration.ofSeconds(60))
                .header("Content-Type", "application/json")
                .header("Accept", "text/event-stream, application/json")
                .header("Authorization", "Bearer " + key)
                .POST(HttpRequest.BodyPublishers.ofString(payload, java.nio.charset.StandardCharsets.UTF_8))
                .build();
    }

    private List<Map<String, Object>> toMessageList(JsonNode messages) {
        if (messages == null || !messages.isArray()) {
            return List.of();
        }
        List<Map<String, Object>> out = new java.util.ArrayList<>();
        for (JsonNode n : messages) {
            if (!n.isObject()) {
                continue;
            }
            Map<String, Object> m = new java.util.LinkedHashMap<>();
            if (n.hasNonNull("role")) {
                m.put("role", n.get("role").asText());
            }
            if (n.hasNonNull("content")) {
                m.put("content", n.get("content").asText());
            }
            out.add(m);
        }
        return out;
    }
}
