package com.xinyu.soulisle.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xinyu.soulisle.entity.ChatMessage;
import com.xinyu.soulisle.entity.EmotionRecord;
import com.xinyu.soulisle.service.MemoryService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.ResponseEntity;

import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyDouble;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * {@code /api/memory/**} 契约守卫（r76；r75 实测本类目标 0% 覆盖、63 行）。
 *
 * <p>这里只锁**控制器的边界行为**：必填字段缺失一律 400、响应形状与计数串、
 * 以及「服务端是权威副本」这条承诺下前端依赖的字段名。落库本身（clamp、limit 归一、
 * 倒序反转）在 {@code MemoryServiceTest} 里锁，跨重启真落库在 {@code _test/j4_memory_check.py} 里锁。
 *
 * <p>MemoryService 用假对象：构建期不起容器、不碰 {@code server/data/} 那份**演示库**
 * （06-constraints 的 env_mode 红线：测试不得写生产/演示数据面）。
 */
class MemoryControllerTest {

    private static final ObjectMapper M = new ObjectMapper();

    private static String text(ResponseEntity<byte[]> r) {
        return new String(r.getBody(), StandardCharsets.UTF_8);
    }

    private static EmotionRecord emotion(long id, String e, double i) {
        EmotionRecord r = new EmotionRecord();
        r.setId(id);
        r.setEmotion(e);
        r.setIntensity(i);
        r.setSecondary("sadness");
        r.setText("今天答辩过了");
        r.setCreatedAt(LocalDateTime.of(2026, 9, 28, 10, 30, 0));
        return r;
    }

    @Test
    @DisplayName("addEmotion：必填齐备则落库并回传该会话累计条数；intensity 非数字时按 0.5 缺省")
    void addEmotionHappyPath() throws Exception {
        MemoryService svc = mock(MemoryService.class);
        when(svc.countEmotions("s1")).thenReturn(3L);
        MemoryController c = new MemoryController(svc);

        JsonNode b = M.readTree(text(c.addEmotion(
                "{\"sessionId\":\"s1\",\"emotion\":\"joy\",\"intensity\":0.8,\"secondary\":\"sadness\",\"text\":\"过了\"}")));
        assertTrue(b.path("ok").asBoolean());
        assertEquals(3, b.path("count").asInt());
        verify(svc).addEmotion("s1", "joy", 0.8, "sadness", "过了");

        // intensity 传进来的是字符串 ⇒ 不是数字，必须落到 0.5 缺省（前端脏数据不打穿落库）
        text(c.addEmotion("{\"sessionId\":\"s1\",\"emotion\":\"joy\",\"intensity\":\"很强烈\"}"));
        verify(svc).addEmotion("s1", "joy", 0.5, null, null);
    }

    @Test
    @DisplayName("addEmotion：缺 sessionId / 缺 emotion / 空体 / 坏 JSON / 非对象 一律 400 且不落库")
    void addEmotionRejectsIncompleteBody() throws Exception {
        MemoryService svc = mock(MemoryService.class);
        MemoryController c = new MemoryController(svc);
        assertEquals(400, c.addEmotion(null).getStatusCode().value());
        assertEquals(400, c.addEmotion("").getStatusCode().value());
        assertEquals(400, c.addEmotion("{\"emotion\":\"joy\"}").getStatusCode().value());
        assertEquals(400, c.addEmotion("{\"sessionId\":\"s1\"}").getStatusCode().value());
        assertEquals(400, c.addEmotion("[1]").getStatusCode().value());
        assertEquals(400, c.addEmotion("{oops").getStatusCode().value());
        assertEquals("{\"error\":\"bad-json\"}", text(c.addEmotion("{\"sessionId\":\"s1\"}")));
        verify(svc, never()).addEmotion(anyString(), anyString(), anyDouble(), any(), any());
    }

    @Test
    @DisplayName("emotions：逐条回传前端曲线要的全部字段，createdAt 为空时不写成当前时间")
    void emotionsMapped() throws Exception {
        MemoryService svc = mock(MemoryService.class);
        when(svc.emotions("s1", 200)).thenReturn(List.of(emotion(1, "joy", 0.7), emotion(2, "calm", 0.3)));
        JsonNode arr = M.readTree(text(new MemoryController(svc).emotions("s1", 200)));
        assertEquals(2, arr.size());
        for (String k : new String[] {"id", "emotion", "intensity", "secondary", "text", "createdAt"}) {
            assertTrue(arr.get(0).has(k), "缺字段 " + k);
        }
        assertEquals("2026-09-28T10:30", arr.get(0).path("createdAt").asText());

        EmotionRecord bare = new EmotionRecord();
        bare.setId(9L);
        when(svc.emotions("s2", 50)).thenReturn(List.of(bare));
        JsonNode arr2 = M.readTree(text(new MemoryController(svc).emotions("s2", 50)));
        assertTrue(arr2.get(0).has("createdAt"), "字段必须在，否则前端读成 undefined");
        assertTrue(arr2.get(0).path("createdAt").isNull(), "createdAt 为空不得伪造当前时间");
    }

    @Test
    @DisplayName("addMessage：role 必填；messages/stats/clear 的响应形状与计数串是前端硬依赖")
    void messageAndStats() throws Exception {
        MemoryService svc = mock(MemoryService.class);
        when(svc.countMessages("s1")).thenReturn(7L);
        MemoryController c = new MemoryController(svc);

        JsonNode added = M.readTree(text(c.addMessage("{\"sessionId\":\"s1\",\"role\":\"user\",\"content\":\"你好\"}")));
        assertTrue(added.path("ok").asBoolean());
        assertEquals(7, added.path("count").asInt());
        verify(svc).addMessage("s1", "user", "你好");

        assertEquals(400, c.addMessage("{\"sessionId\":\"s1\"}").getStatusCode().value());
        assertEquals(400, c.addMessage("{\"role\":\"user\"}").getStatusCode().value());
        assertEquals(400, c.addMessage("null").getStatusCode().value());

        ChatMessage m = new ChatMessage();
        m.setId(1L);
        m.setRole("assistant");
        m.setContent("我在");
        m.setCreatedAt(LocalDateTime.of(2026, 9, 29, 1, 2, 3));
        when(svc.messages("s1", 40)).thenReturn(List.of(m));
        JsonNode arr = M.readTree(text(c.messages("s1", 40)));
        assertEquals("assistant", arr.get(0).path("role").asText());
        assertEquals("我在", arr.get(0).path("content").asText());
        assertEquals("2026-09-29T01:02:03", arr.get(0).path("createdAt").asText());

        when(svc.countEmotions("s1")).thenReturn(4L);
        JsonNode st = M.readTree(text(c.stats("s1")));
        assertEquals("s1", st.path("sessionId").asText());
        assertEquals(4, st.path("emotions").asInt());
        assertEquals(7, st.path("messages").asInt());

        when(svc.clear("s1")).thenReturn(11);
        JsonNode cleared = M.readTree(text(c.clear("s1")));
        assertEquals(11, cleared.path("removed").asInt());
    }

    @Test
    @DisplayName("r77 边界补形：顶层是 null/数组也判 bad-json；createdAt 有值时给 ISO 串而不是对象")
    void parseShapeAndCreatedAtString() throws Exception {
        MemoryService svc = mock(MemoryService.class);
        MemoryController c = new MemoryController(svc);

        assertEquals(400, c.addEmotion("null").getStatusCode().value(), "JSON 字面量 null 不是对象");
        assertEquals(400, c.addEmotion("[{\"sessionId\":\"s1\"}]").getStatusCode().value());
        assertEquals(400, c.addMessage("null").getStatusCode().value());
        verify(svc, never()).addEmotion(anyString(), anyString(), anyDouble(), any(), any());

        ChatMessage stamped = new ChatMessage();
        stamped.setId(9L);
        stamped.setRole("user");
        stamped.setContent("你好");
        stamped.setCreatedAt(LocalDateTime.of(2026, 9, 29, 1, 2, 3));
        when(svc.messages("s1", 40)).thenReturn(List.of(stamped));
        JsonNode list = M.readTree(text(c.messages("s1", 40)));
        assertEquals("2026-09-29T01:02:03", list.get(0).path("createdAt").asText(),
                "前端直接把这个字符串画进时间线 ⇒ 形态不能随驱动侧漂移");

        // intensity 给了但不是数字：与「没给」同义，取 0.5 中值，不得把字符串塞进 double
        assertEquals(200, c.addEmotion("{\"sessionId\":\"s1\",\"emotion\":\"joy\",\"intensity\":\"很高\"}")
                .getStatusCode().value());
        verify(svc).addEmotion("s1", "joy", 0.5, null, null);
    }

    @Test
    @DisplayName("r83 补形：intensity 键不存在 与 ChatMessage 落库时间为空 是两个真分支，不靠缺省值蒙绿")
    void absentIntensityKeyAndStaleMessageTimestamp() throws Exception {
        MemoryService svc = mock(MemoryService.class);
        MemoryController c = new MemoryController(svc);

        // 「has(intensity)==false」与「has 但不是数字」走不同短路，结果必须同为 0.5
        assertEquals(200, c.addEmotion("{\"sessionId\":\"s1\",\"emotion\":\"joy\"}").getStatusCode().value());
        verify(svc).addEmotion("s1", "joy", 0.5, null, null);

        ChatMessage stale = new ChatMessage();
        stale.setId(11L);
        stale.setRole("user");
        stale.setContent("你好");
        when(svc.messages("s9", 40)).thenReturn(List.of(stale));
        JsonNode list = M.readTree(text(c.messages("s9", 40)));
        assertTrue(list.get(0).has("createdAt"), "字段必须在，否则前端时间线读成 undefined");
        assertTrue(list.get(0).path("createdAt").isNull(), "落库时间缺失时不得伪造当前时间");
    }

    @Test
    @DisplayName("r83 不可达腿留证：readTree 对空串/空白只给 MissingNode，永不返回 null")
    void parseNeverReturnsJavaNullSoThatSideIsUnreachable() throws Exception {
        // MemoryController.parse / ChatController / EmotionController 三处都有 `node == null` 这一侧，
        // jacoco 常年报它 missed。这里把「为什么不可达」钉成用例而不是散文：
        // 只要 Jackson 哪天让 readTree 真返回 null，这条先红，三处的「不可达」归类随即失效。
        assertNotNull(M.readTree(""),
                "空串必须是 MissingNode（非 null），否则三处控制器的 null 侧不再是死代码");
        assertNotNull(M.readTree("   "));
        assertFalse(M.readTree("").isObject(), "非对象侧仍然可达，缺省判断才有意义");
        assertTrue(M.readTree("{}").isObject());
    }
}
