package com.xinyu.soulisle.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xinyu.soulisle.llm.LlmProxy;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.nio.charset.StandardCharsets;

/**
 * {@code POST /api/chat} —— v1 契约 1:1 复刻（对照 deploy/functions/api/chat.js）。
 *
 * <p>请求体只认 {@code messages / temperature / max_tokens} 三个字段；
 * 响应体是上游 OpenAI 兼容响应**逐字透传**，前端解析路径零改动。
 */
@RestController
public class ChatController {

    private final ObjectMapper mapper = new ObjectMapper();
    private final LlmProxy proxy;

    public ChatController(LlmProxy proxy) {
        this.proxy = proxy;
    }

    @PostMapping("/api/chat")
    public ResponseEntity<byte[]> chat(@RequestBody(required = false) String raw) {
        if (!proxy.hasKey()) {
            return json(500, "{\"error\":\"no-key\"}");
        }

        JsonNode node;
        try {
            node = mapper.readTree(raw == null ? "" : raw);
        } catch (Exception e) {
            return json(400, "{\"error\":\"bad-json\"}");
        }
        if (node == null || !node.isObject()) {
            return json(400, "{\"error\":\"bad-json\"}");
        }

        JsonNode messages = node.get("messages");
        JsonNode tempNode = node.get("temperature");
        JsonNode maxNode = node.get("max_tokens");
        Double temperature = (tempNode != null && tempNode.isNumber()) ? tempNode.asDouble() : null;
        Integer maxTokens = (maxNode != null && maxNode.isNumber()) ? maxNode.asInt() : null;

        LlmProxy.Result r = proxy.call(messages, temperature, maxTokens);
        return json(r.status(), r.body());
    }

    /** 以 UTF-8 字节直写，绕开 StringHttpMessageConverter 的默认字符集坑（中文回复必须原样回传） */
    private ResponseEntity<byte[]> json(int status, String body) {
        return ResponseEntity.status(status)
                .contentType(MediaType.APPLICATION_JSON)
                .body(body.getBytes(StandardCharsets.UTF_8));
    }
}
