package com.xinyu.soulisle.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xinyu.soulisle.llm.LlmProxy;
import com.xinyu.soulisle.safety.SafetyGuard;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.nio.charset.StandardCharsets;

/**
 * {@code POST /api/chat} —— v1 契约 1:1 复刻（对照 deploy/functions/api/chat.js）。
 *
 * <p>请求体认 {@code messages / temperature / max_tokens}（v1 三字段）+ 可选 {@code stream}。
 * <p>{@code stream} 缺省或非 true → 上游响应**逐字透传** JSON，前端解析路径零改动（AC-OBS-08）。
 * <p>{@code stream:true} 且上游真是 SSE → 以 {@code text/event-stream} 逐块直通；
 * 其余情况（上游报错/不支持流式）自动折回整包 JSON，前端按 content-type 回落，不产生半成品气泡。
 */
@RestController
public class ChatController {

    private final ObjectMapper mapper = new ObjectMapper();
    private final LlmProxy proxy;

    public ChatController(LlmProxy proxy) {
        this.proxy = proxy;
    }

    /**
     * 返回类型必须是 **{@code ResponseEntity<StreamingResponseBody>}**（不是 {@code ResponseEntity<?>}）。
     * 实测教训：声明成 {@code ?} 时 Spring 解析出的 body 类型是 Object，流式分支会报
     * {@code No converter for [...Lambda...] with preset Content-Type 'text/event-stream'} → HTTP 500。
     * 整包 JSON 同样用 StreamingResponseBody 写（字节逐字不变），保证两条分支共用一个出口、一个签名。
     */
    @PostMapping("/api/chat")
    public ResponseEntity<StreamingResponseBody> chat(@RequestBody(required = false) String raw) {
        if (!proxy.hasKey()) {
            return bytes(500, MediaType.APPLICATION_JSON, "{\"error\":\"no-key\"}");
        }

        JsonNode node;
        try {
            node = mapper.readTree(raw == null ? "" : raw);
        } catch (Exception e) {
            return bytes(400, MediaType.APPLICATION_JSON, "{\"error\":\"bad-json\"}");
        }
        if (node == null || !node.isObject()) {
            return bytes(400, MediaType.APPLICATION_JSON, "{\"error\":\"bad-json\"}");
        }

        JsonNode messages = node.get("messages");
        JsonNode tempNode = node.get("temperature");
        JsonNode maxNode = node.get("max_tokens");
        Double temperature = (tempNode != null && tempNode.isNumber()) ? tempNode.asDouble() : null;
        Integer maxTokens = (maxNode != null && maxNode.isNumber()) ? maxNode.asInt() : null;
        boolean wantStream = node.path("stream").isBoolean() && node.get("stream").asBoolean();

        // r38 输入侧护栏：**只改上行 messages，响应体仍逐字透传**（AC-OBS-08 契约不破）。
        // 干净输入下 harden() 原样返回同一对象 ⇒ 常规对话零行为差异；判定结果只落到响应头。
        SafetyGuard.Verdict verdict = SafetyGuard.scan(SafetyGuard.lastUserText(messages));
        JsonNode upMessages = SafetyGuard.harden(messages);
        String safety = SafetyGuard.headerValue(verdict);

        if (!wantStream) {
            LlmProxy.Result r = proxy.call(upMessages, temperature, maxTokens);
            return bytes(r.status(), MediaType.APPLICATION_JSON, r.body(), safety);
        }

        LlmProxy.StreamResult s = proxy.openStream(upMessages, temperature, maxTokens);
        if (!s.isEventStream()) {
            return bytes(s.status(), MediaType.APPLICATION_JSON, s.body(), safety);
        }
        StreamingResponseBody body = out -> {
            try (java.io.InputStream in = s.bodyStream()) {
                byte[] buf = new byte[2048];
                int n;
                while ((n = in.read(buf)) != -1) {
                    out.write(buf, 0, n);
                    out.flush();               // 逐块下发：攒满缓冲区再返回就失去流式意义
                }
            }
        };
        return ResponseEntity.status(200)
                .header("Content-Type", "text/event-stream;charset=UTF-8")
                .header("Cache-Control", "no-cache, no-transform")
                .header("X-Accel-Buffering", "no")
                .header("X-Xinyu-Safety", safety)
                .body(body);
    }

    /** 以 UTF-8 字节直写，绕开 StringHttpMessageConverter 的默认字符集坑（中文回复必须原样回传） */
    private ResponseEntity<StreamingResponseBody> bytes(int status, MediaType type, String body) {
        return bytes(status, type, body, null);
    }

    private ResponseEntity<StreamingResponseBody> bytes(int status, MediaType type, String body, String safety) {
        byte[] data = body.getBytes(StandardCharsets.UTF_8);
        ResponseEntity.BodyBuilder b = ResponseEntity.status(status).contentType(type);
        if (safety != null) {
            b = b.header("X-Xinyu-Safety", safety);   // 头里带判定，body 一字不改
        }
        return b.body(out -> out.write(data));
    }
}
