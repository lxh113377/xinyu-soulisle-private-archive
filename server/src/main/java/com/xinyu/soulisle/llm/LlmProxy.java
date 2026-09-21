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
        Map<String, Object> upstreamBody = new java.util.LinkedHashMap<>();
        upstreamBody.put("model", model);
        upstreamBody.put("messages", toMessageList(messages));
        upstreamBody.put("temperature", temperature == null ? DEFAULT_TEMPERATURE : temperature);
        upstreamBody.put("max_tokens", maxTokens == null ? DEFAULT_MAX_TOKENS : maxTokens);

        String payload;
        try {
            payload = mapper.writeValueAsString(upstreamBody);
        } catch (Exception e) {
            return new Result(500, "{\"error\":\"bad-json\"}");
        }

        String url = base.replaceAll("/$", "") + "/chat/completions";
        HttpRequest req = HttpRequest.newBuilder(URI.create(url))
                .timeout(Duration.ofSeconds(60))
                .header("Content-Type", "application/json")
                .header("Authorization", "Bearer " + key)
                .POST(HttpRequest.BodyPublishers.ofString(payload, java.nio.charset.StandardCharsets.UTF_8))
                .build();

        try {
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString(
                    java.nio.charset.StandardCharsets.UTF_8));
            String body = resp.body();
            if (body == null || body.isBlank()) {
                return new Result(resp.statusCode(), "{\"error\":\"upstream-nonjson\"}");
            }
            return new Result(resp.statusCode(), body);
        } catch (Exception e) {
            return new Result(502, "{\"error\":\"upstream-error\"}");
        }
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
