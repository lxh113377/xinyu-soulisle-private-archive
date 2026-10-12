package com.xinyu.soulisle.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xinyu.soulisle.entity.ChatMessage;
import com.xinyu.soulisle.entity.EmotionRecord;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * r130：记忆可携带（导出/导入）的判据。
 *
 * <p>最要紧的一条是**幂等**：换机器时用户会「导一次、不确定、再导一次」，
 * 不幂等的导入会在几秒内把历史翻倍 —— 那比导入失败更糟，因为它看起来是成功的。
 */
class MemoryPortServiceTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static JsonNode json(String s) {
        try {
            return MAPPER.readTree(s);
        } catch (Exception e) {
            throw new IllegalArgumentException(e);
        }
    }

    private static ChatMessage msg(String role, String content) {
        ChatMessage m = new ChatMessage();
        m.setRole(role);
        m.setContent(content);
        m.setCreatedAt(LocalDateTime.of(2026, 10, 12, 10, 0));
        return m;
    }

    private static EmotionRecord emo(String emotion, String text) {
        EmotionRecord r = new EmotionRecord();
        r.setEmotion(emotion);
        r.setIntensity(0.6);
        r.setText(text);
        r.setCreatedAt(LocalDateTime.of(2026, 10, 12, 10, 0));
        return r;
    }

    private static MemoryService memoryWith(List<ChatMessage> msgs, List<EmotionRecord> emos) {
        MemoryService memory = mock(MemoryService.class);
        when(memory.messages(anyString(), anyInt())).thenReturn(msgs);
        when(memory.emotions(anyString(), anyInt())).thenReturn(emos);
        return memory;
    }

    @Test
    @DisplayName("导出件带 schema/计数/两类条目，时间可序列化")
    void exportCarriesSchemaAndItems() {
        MemoryService memory = memoryWith(List.of(msg("user", "你好")), List.of(emo("joy", "今天不错")));
        MemoryPortService port = new MemoryPortService(memory);

        Map<String, Object> body = port.exportSession("s1", 500);

        assertEquals(MemoryPortService.SCHEMA, body.get("schema"));
        assertEquals("s1", body.get("sessionId"));
        @SuppressWarnings("unchecked")
        Map<String, Object> counts = (Map<String, Object>) body.get("counts");
        assertEquals(1, counts.get("messages"));
        assertEquals(1, counts.get("emotions"));
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> ms = (List<Map<String, Object>>) body.get("messages");
        assertEquals("你好", ms.get(0).get("content"));
        assertNotNull(ms.get(0).get("createdAt"));
    }

    @Test
    @DisplayName("不给 sessionId 的导出返回 null（控制器转 400）—— 不给匿名端点开全量下载")
    void exportRequiresSession() {
        MemoryPortService port = new MemoryPortService(memoryWith(List.of(), List.of()));
        assertNull(port.exportSession(null, 500));
        assertNull(port.exportSession("   ", 500));
    }

    @Test
    @DisplayName("schema 不匹配逐字拒绝，并回传期望值与实际值")
    void rejectsSchemaMismatch() {
        MemoryPortService port = new MemoryPortService(memoryWith(List.of(), List.of()));

        Map<String, Object> out = port.importPayload(json("{\"schema\":\"xinyu-memory/0\",\"sessionId\":\"s1\"}"));

        assertEquals("schema-mismatch", out.get("error"));
        assertEquals(MemoryPortService.SCHEMA, out.get("expected"));
        assertEquals("xinyu-memory/0", out.get("got"));
    }

    @Test
    @DisplayName("坏形态（null / 非对象 / 缺 sessionId）统一判 bad-json")
    void rejectsMalformedPayloads() {
        MemoryPortService port = new MemoryPortService(memoryWith(List.of(), List.of()));
        assertEquals("bad-json", port.importPayload(null).get("error"));
        assertEquals("bad-json", port.importPayload(json("[1,2]")).get("error"));
        assertEquals("bad-json", port.importPayload(json("{\"schema\":\"xinyu-memory/1\"}")).get("error"));
    }

    @Test
    @DisplayName("单批超 500 条直接拒绝：宁可整批不导，也不要导入一半")
    void rejectsOversizedBatch() {
        MemoryPortService port = new MemoryPortService(memoryWith(List.of(), List.of()));
        StringBuilder sb = new StringBuilder("{\"schema\":\"xinyu-memory/1\",\"sessionId\":\"s1\",\"messages\":[");
        for (int i = 0; i < 501; i++) {
            sb.append(i > 0 ? "," : "").append("{\"role\":\"user\",\"content\":\"c").append(i).append("\"}");
        }
        sb.append("]}");

        Map<String, Object> out = port.importPayload(json(sb.toString()));

        assertEquals("too-many-items", out.get("error"));
        assertEquals(500, out.get("limit"));
    }

    @Test
    @DisplayName("正常导入：两条消息写入成功")
    void importsMessages() {
        MemoryService memory = memoryWith(new ArrayList<>(), new ArrayList<>());
        MemoryPortService port = new MemoryPortService(memory);

        Map<String, Object> out = port.importPayload(json(
                "{\"schema\":\"xinyu-memory/1\",\"sessionId\":\"s1\",\"messages\":["
                        + "{\"role\":\"user\",\"content\":\"在吗\"},"
                        + "{\"role\":\"assistant\",\"content\":\"我在\"}]}"));

        assertEquals(2, out.get("inserted"));
        assertEquals(0, out.get("skipped"));
        assertEquals(0, out.get("rejected"));
        verify(memory, times(2)).addMessage(eq("s1"), anyString(), anyString());
    }

    @Test
    @DisplayName("幂等：同内容再导一次全 skipped，不产生第二条")
    void importIsIdempotent() {
        List<ChatMessage> existing = new ArrayList<>(List.of(msg("user", "在吗")));
        MemoryService memory = memoryWith(existing, new ArrayList<>());
        MemoryPortService port = new MemoryPortService(memory);

        Map<String, Object> out = port.importPayload(json(
                "{\"schema\":\"xinyu-memory/1\",\"sessionId\":\"s1\",\"messages\":[{\"role\":\"user\",\"content\":\"在吗\"}]}"));

        assertEquals(0, out.get("inserted"), "已存在的那条不得再插一遍");
        assertEquals(1, out.get("skipped"));
        verify(memory, times(0)).addMessage(anyString(), anyString(), anyString());
    }

    @Test
    @DisplayName("批次内自身重复也算 skipped（同一批里两条一样的内容只落一条）")
    void dedupesWithinBatch() {
        MemoryService memory = memoryWith(new ArrayList<>(), new ArrayList<>());
        MemoryPortService port = new MemoryPortService(memory);

        Map<String, Object> out = port.importPayload(json(
                "{\"schema\":\"xinyu-memory/1\",\"sessionId\":\"s1\",\"messages\":["
                        + "{\"role\":\"user\",\"content\":\"重复\"},{\"role\":\"user\",\"content\":\"重复\"}]}"));

        assertEquals(1, out.get("inserted"));
        assertEquals(1, out.get("skipped"));
    }

    @Test
    @DisplayName("非法条目计入 rejected 且不落库：角色非 user/assistant、内容空白、情绪名为空")
    void rejectsInvalidItems() {
        MemoryService memory = memoryWith(new ArrayList<>(), new ArrayList<>());
        MemoryPortService port = new MemoryPortService(memory);

        Map<String, Object> out = port.importPayload(json(
                "{\"schema\":\"xinyu-memory/1\",\"sessionId\":\"s1\",\"messages\":["
                        + "{\"role\":\"root\",\"content\":\"越权角色\"},"
                        + "{\"role\":\"user\",\"content\":\"   \"},"
                        + "{\"role\":\"user\",\"content\":\"正常\"}],"
                        + "\"emotions\":[{\"emotion\":\"\"},{\"emotion\":\"joy\",\"intensity\":0.3}]}"));

        assertEquals(3, out.get("rejected"), "非法消息 2 条 + 空情绪名 1 条");
        assertEquals(2, out.get("inserted"), "正常消息 1 条 + 合法情绪 1 条");
    }

    @Test
    @DisplayName("intensity 缺失或非数字时按 0.5 落库，不把 NaN 写进库")
    void defaultsIntensity() {
        MemoryService memory = memoryWith(new ArrayList<>(), new ArrayList<>());
        MemoryPortService port = new MemoryPortService(memory);

        port.importPayload(json(
                "{\"schema\":\"xinyu-memory/1\",\"sessionId\":\"s1\","
                        + "\"emotions\":[{\"emotion\":\"calm\",\"text\":\"还行\"}]}"));

        verify(memory).addEmotion(eq("s1"), eq("calm"), eq(0.5), org.mockito.ArgumentMatchers.isNull(), eq("还行"));
    }

    @Test
    @DisplayName("messages/emotions 不是数组时按空处理：不抛、不导入")
    void toleratesNonArrayFields() {
        MemoryService memory = memoryWith(new ArrayList<>(), new ArrayList<>());
        MemoryPortService port = new MemoryPortService(memory);

        Map<String, Object> out = port.importPayload(json(
                "{\"schema\":\"xinyu-memory/1\",\"sessionId\":\"s1\",\"messages\":{\"a\":1},\"emotions\":null}"));

        assertTrue(Boolean.TRUE.equals(out.get("ok")), "空批次也是成功，只是 0 条");
        assertEquals(0, out.get("inserted"));
    }
}
