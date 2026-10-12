package com.xinyu.soulisle.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xinyu.soulisle.service.MemoryPortService;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.nio.charset.StandardCharsets;
import java.util.Map;

/**
 * 记忆导出/导入（r130 新增）：数据可携带权的两个端点，逻辑在 {@link MemoryPortService}。
 *
 * <p><b>为什么单独开一个控制器而不是加进 {@code MemoryController}</b>：往既有控制器里塞方法
 * 要改它的构造签名，等于动 7 个既有测试的装配面。能力位是新开的、契约是新增的，
 * 单独一个类 ⇒ 既有面零改动、零回归风险；读者也能一眼看出「这一组是本轮新增」。
 *
 * <p><b>安全边界</b>：导出<b>必须</b>给 {@code sessionId}（不给就 400），
 * 刻意不提供「不传参数就导出全库」的形态 —— 那等于给任何拿到地址的人开全量数据下载。
 */
@RestController
public class MemoryPortController {

    private final ObjectMapper mapper = new ObjectMapper();
    private final MemoryPortService port;

    public MemoryPortController(MemoryPortService port) {
        this.port = port;
    }

    @GetMapping("/api/memory/export")
    public ResponseEntity<byte[]> exportMemory(@RequestParam(required = false) String sessionId,
                                               @RequestParam(defaultValue = "500") int limit) {
        Map<String, Object> body = port.exportSession(sessionId, limit);
        if (body == null) {
            return json(400, "{\"error\":\"bad-json\"}");
        }
        return json(200, write(body));
    }

    @PostMapping("/api/memory/import")
    public ResponseEntity<byte[]> importMemory(@RequestBody(required = false) String raw) {
        JsonNode n = parse(raw);
        Map<String, Object> body = port.importPayload(n);
        int status = body.containsKey("error") ? 400 : 200;
        return json(status, write(body));
    }

    private JsonNode parse(String raw) {
        try {
            JsonNode n = mapper.readTree(raw == null ? "" : raw);
            return (n != null && n.isObject()) ? n : null;
        } catch (Exception e) {
            return null;
        }
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
