package com.xinyu.soulisle.engine;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

/**
 * 本地情绪模型代理（三级路由的中坚腿）。
 *
 * <p>调用 Python 侧 FastAPI 服务（{@code ml/server.py}，默认 {@code 127.0.0.1:8300}）：
 * 请求 {@code POST /classify {"text":"..."}}，响应
 * {@code {"emotion":"...","intensity":0.x,"confidence":0.x,"latency_ms":x.x}}。
 *
 * <p>语义与 {@link com.xinyu.soulisle.llm.LlmProxy} 同款：**任何失败（未配置 / 连不上 /
 * 超时 / 非 200 / 坏 JSON / 非法情绪名）一律返回 null，不抛异常** —— 路由层拿到 null
 * 就自动降级到下一腿，本地模型挂掉绝不能影响对话主链路。
 */
@Component
public class ModelProxy {

    private static final org.slf4j.Logger LOGGER =
            org.slf4j.LoggerFactory.getLogger(ModelProxy.class);

    /** 本地模型判定结果（confidence = softmax top-1 概率） */
    public record Verdict(String emotion, double intensity, double confidence) {}

    private static final int MAX_TEXT_LEN = 200;

    private final ObjectMapper mapper = new ObjectMapper();
    private final HttpClient http;
    private final String url;

    public ModelProxy(@Value("${xinyu.emotion.model-url:}") String url,
                      @Value("${xinyu.emotion.model-timeout-ms:1500}") long timeoutMs) {
        this.url = url == null ? "" : url.trim().replaceAll("/$", "");
        this.http = HttpClient.newBuilder()
                // 强制 HTTP/1.1：默认 HTTP_2 会在首请求带 Upgrade: h2c 头，uvicorn(h11)
                // 解析该头时丢弃 body → FastAPI 422 "body missing"
                // （2026-10-09 一手实测：422 input=null；NO_PROXY 修不掉，HTTP_1_1 一次修掉）
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofMillis(Math.max(200, timeoutMs)))
                // 回环服务直连：JDK HttpClient 默认继承系统代理，会把本机请求转手代理
                .proxy(HttpClient.Builder.NO_PROXY)
                .build();
        this.timeoutMs = Math.max(200, timeoutMs);
    }

    private final long timeoutMs;

    /** 是否配置了本地模型服务（未配置 = 路由直接跳过本地腿，行为与旧双路完全一致） */
    public boolean enabled() {
        return !url.isEmpty();
    }

    /**
     * @return 判定结果；任何失败返回 null（含未配置时直接 null，调用方应先用 {@link #enabled()} 区分）
     */
    public Verdict classify(String text) {
        if (!enabled()) {
            return null;
        }
        String payload;
        try {
            payload = mapper.writeValueAsString(
                    java.util.Map.of("text", text == null ? "" : text.substring(0, Math.min(MAX_TEXT_LEN, text.length()))));
        } catch (Exception e) {
            return null;
        }
        HttpRequest req = HttpRequest.newBuilder(URI.create(url + "/classify"))
                .timeout(Duration.ofMillis(timeoutMs))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(payload,
                        java.nio.charset.StandardCharsets.UTF_8))
                .build();
        try {
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString(
                    java.nio.charset.StandardCharsets.UTF_8));
            if (resp.statusCode() != 200) {
                LOGGER.warn("local model classify: non-200 status={} body={}",
                        resp.statusCode(), resp.body());
                return null;
            }
            String body = resp.body();
            if (body == null || body.isBlank()) {
                LOGGER.warn("local model classify: empty body");
                return null;
            }
            JsonNode j = mapper.readTree(body);
            String emotion = j.path("emotion").asText("");
            if (!EmotionLexicon.EMOTIONS.contains(emotion)) {
                LOGGER.warn("local model classify: bad-emotion in body={}", body);
                return null;
            }
            JsonNode conf = j.get("confidence");
            if (conf == null || !conf.isNumber()) {
                LOGGER.warn("local model classify: confidence missing/non-number in body={}", body);
                return null;
            }
            double confidence = Math.max(0, Math.min(1, conf.asDouble()));
            double intensity = j.has("intensity") && j.get("intensity").isNumber()
                    ? j.get("intensity").asDouble() : 0.5;
            intensity = Math.max(0, Math.min(1, intensity));
            return new Verdict(emotion, intensity, confidence);
        } catch (Exception e) {
            LOGGER.warn("local model classify failed (url={}): {}", url, e.toString());
            return null;
        }
    }
}
