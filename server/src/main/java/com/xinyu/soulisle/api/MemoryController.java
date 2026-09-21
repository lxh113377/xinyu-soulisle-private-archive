package com.xinyu.soulisle.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xinyu.soulisle.entity.ChatMessage;
import com.xinyu.soulisle.entity.EmotionRecord;
import com.xinyu.soulisle.service.MemoryService;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 记忆持久化 API（J4）。
 *
 * <p>会话隔离靠 {@code sessionId}（前端生成并持久在 localStorage）；
 * 与 v1 一致的原则：服务端是权威副本，前端本地保留为降级路径。
 */
@RestController
public class MemoryController {

    private final ObjectMapper mapper = new ObjectMapper();
    private final MemoryService memory;

    public MemoryController(MemoryService memory) {
        this.memory = memory;
    }

    @PostMapping("/api/memory/emotion")
    public ResponseEntity<byte[]> addEmotion(@RequestBody(required = false) String raw) {
        JsonNode n = parse(raw);
        String sessionId = text(n, "sessionId");
        String emotion = text(n, "emotion");
        if (sessionId == null || emotion == null) {
            return json(400, "{\"error\":\"bad-json\"}");
        }
        double intensity = n.has("intensity") && n.get("intensity").isNumber() ? n.get("intensity").asDouble() : 0.5;
        memory.addEmotion(sessionId, emotion, intensity, text(n, "secondary"), text(n, "text"));
        return json(200, "{\"ok\":true,\"count\":" + memory.countEmotions(sessionId) + "}");
    }

    @GetMapping("/api/memory/emotions")
    public ResponseEntity<byte[]> emotions(@RequestParam String sessionId,
                                           @RequestParam(defaultValue = "200") int limit) {
        List<EmotionRecord> list = memory.emotions(sessionId, limit);
        List<Map<String, Object>> out = new ArrayList<>();
        for (EmotionRecord r : list) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("id", r.getId());
            m.put("emotion", r.getEmotion());
            m.put("intensity", r.getIntensity());
            m.put("secondary", r.getSecondary());
            m.put("text", r.getText());
            m.put("createdAt", r.getCreatedAt() == null ? null : r.getCreatedAt().toString());
            out.add(m);
        }
        return json(200, write(out));
    }

    @PostMapping("/api/memory/message")
    public ResponseEntity<byte[]> addMessage(@RequestBody(required = false) String raw) {
        JsonNode n = parse(raw);
        String sessionId = text(n, "sessionId");
        String role = text(n, "role");
        if (sessionId == null || role == null) {
            return json(400, "{\"error\":\"bad-json\"}");
        }
        memory.addMessage(sessionId, role, text(n, "content"));
        return json(200, "{\"ok\":true,\"count\":" + memory.countMessages(sessionId) + "}");
    }

    @GetMapping("/api/memory/messages")
    public ResponseEntity<byte[]> messages(@RequestParam String sessionId,
                                           @RequestParam(defaultValue = "40") int limit) {
        List<ChatMessage> list = memory.messages(sessionId, limit);
        List<Map<String, Object>> out = new ArrayList<>();
        for (ChatMessage m : list) {
            Map<String, Object> x = new LinkedHashMap<>();
            x.put("id", m.getId());
            x.put("role", m.getRole());
            x.put("content", m.getContent());
            x.put("createdAt", m.getCreatedAt() == null ? null : m.getCreatedAt().toString());
            out.add(x);
        }
        return json(200, write(out));
    }

    /** 一键清除该会话全部数据（对应前端「清除我的数据」） */
    @DeleteMapping("/api/memory/{sessionId}")
    public ResponseEntity<byte[]> clear(@PathVariable String sessionId) {
        int removed = memory.clear(sessionId);
        return json(200, "{\"ok\":true,\"removed\":" + removed + "}");
    }

    @GetMapping("/api/memory/stats")
    public ResponseEntity<byte[]> stats(@RequestParam String sessionId) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("sessionId", sessionId);
        body.put("emotions", memory.countEmotions(sessionId));
        body.put("messages", memory.countMessages(sessionId));
        return json(200, write(body));
    }

    private JsonNode parse(String raw) {
        try {
            JsonNode n = mapper.readTree(raw == null ? "" : raw);
            return (n != null && n.isObject()) ? n : null;
        } catch (Exception e) {
            return null;
        }
    }

    private String text(JsonNode n, String field) {
        if (n == null || !n.hasNonNull(field)) {
            return null;
        }
        return n.get(field).asText();
    }

    private String write(Object o) {
        try {
            return mapper.writeValueAsString(o);
        } catch (Exception e) {
            return "{\"error\":\"serialize\"}";
        }
    }

    private ResponseEntity<byte[]> json(int status, String body) {
        return ResponseEntity.status(status)
                .contentType(MediaType.APPLICATION_JSON)
                .body(body.getBytes(StandardCharsets.UTF_8));
    }
}
