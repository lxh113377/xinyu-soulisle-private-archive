package com.xinyu.soulisle.service;

import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.conditions.Wrapper;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.xinyu.soulisle.entity.ChatMessage;
import com.xinyu.soulisle.entity.EmotionRecord;
import com.xinyu.soulisle.mapper.ChatMessageMapper;
import com.xinyu.soulisle.mapper.EmotionRecordMapper;
import org.apache.ibatis.builder.MapperBuilderAssistant;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 记忆落库层的边界守卫（r76；r75 实测本类目标 0% 覆盖、47 行）。
 *
 * <p>锁三件最容易在重构中被改坏的事：
 * ① <b>超长截断</b>（情绪 200 / 消息 2000）——列宽是 DDL 定的，写超了是插入报错而不是优雅降级；
 * ② <b>limit 归一</b>（≤0 走 200、上限 500）——它直接拼进 SQL 的 LIMIT，不合法入参不能原样下传；
 * ③ <b>倒序取再反转</b>——前端情绪曲线按时间正序画，忘了反转就是整条曲线上下颠倒。
 *
 * <p>mapper 用假对象，构建期不起容器、不碰 {@code server/data/} 演示库；
 * 真落库与跨重启不丢由 {@code _test/j4_memory_check.py} 带外核验。
 */
class MemoryServiceTest {

    /**
     * MyBatis-Plus 的 lambda 条件（{@code eq(EmotionRecord::getSessionId, …)}）靠实体列缓存解析，
     * 该缓存由容器扫描实体时安装。构建期不起容器 ⇒ 不先装缓存，被测方法会在**进入业务逻辑之前**
     * 抛 {@code can not find lambda cache for this entity}（r76 首跑实测）。
     * 这里只做「让缓存就位」这一件事，不引入数据源、不连演示库。
     */
    @BeforeAll
    static void installColumnCache() {
        MapperBuilderAssistant assistant = new MapperBuilderAssistant(new MybatisConfiguration(), "");
        assistant.setCurrentNamespace("com.xinyu.soulisle.mapper");
        TableInfoHelper.initTableInfo(assistant, EmotionRecord.class);
        TableInfoHelper.initTableInfo(assistant, ChatMessage.class);
    }

    private static EmotionRecord rec(long id) {
        EmotionRecord r = new EmotionRecord();
        r.setId(id);
        r.setEmotion("joy");
        return r;
    }

    private static ChatMessage msg(long id) {
        ChatMessage m = new ChatMessage();
        m.setId(id);
        m.setRole("user");
        return m;
    }

    @Test
    @DisplayName("addEmotion：字段齐备落库；text 超 200 截断、null 折成空串、createdAt 由服务端盖章")
    void addEmotionClampsAndStamps() {
        EmotionRecordMapper em = mock(EmotionRecordMapper.class);
        MemoryService svc = new MemoryService(em, mock(ChatMessageMapper.class));

        svc.addEmotion("s1", "joy", 0.62, "calm", "短文本");
        ArgumentCaptor<EmotionRecord> cap = ArgumentCaptor.forClass(EmotionRecord.class);
        verify(em).insert(cap.capture());
        EmotionRecord saved = cap.getValue();
        assertEquals("s1", saved.getSessionId());
        assertEquals("joy", saved.getEmotion());
        assertEquals(0.62, saved.getIntensity(), 1e-9);
        assertEquals("calm", saved.getSecondary());
        assertEquals("短文本", saved.getText());
        assertNotNull(saved.getCreatedAt(), "时间戳必须由服务端生成，否则曲线没有时间轴");

        svc.addEmotion("s1", "sadness", 0.3, null, "啊".repeat(500));
        ArgumentCaptor<EmotionRecord> cap2 = ArgumentCaptor.forClass(EmotionRecord.class);
        verify(em, org.mockito.Mockito.times(2)).insert(cap2.capture());
        assertEquals(200, cap2.getAllValues().get(1).getText().length(), "列宽 200，写超会插入报错");

        svc.addEmotion("s1", "calm", 0.1, null, null);
        ArgumentCaptor<EmotionRecord> cap3 = ArgumentCaptor.forClass(EmotionRecord.class);
        verify(em, org.mockito.Mockito.times(3)).insert(cap3.capture());
        assertEquals("", cap3.getAllValues().get(2).getText(), "null 必须折成空串，不能原样落库");
    }

    @Test
    @DisplayName("addMessage：content 超 2000 截断、null 折空串；role/sessionId 原样保留")
    void addMessageClamps() {
        ChatMessageMapper mm = mock(ChatMessageMapper.class);
        MemoryService svc = new MemoryService(mock(EmotionRecordMapper.class), mm);

        svc.addMessage("s1", "assistant", "好的".repeat(1500));
        ArgumentCaptor<ChatMessage> cap = ArgumentCaptor.forClass(ChatMessage.class);
        verify(mm).insert(cap.capture());
        assertEquals(2000, cap.getValue().getContent().length());
        assertEquals("assistant", cap.getValue().getRole());

        svc.addMessage("s1", "user", null);
        ArgumentCaptor<ChatMessage> cap2 = ArgumentCaptor.forClass(ChatMessage.class);
        verify(mm, org.mockito.Mockito.times(2)).insert(cap2.capture());
        assertEquals("", cap2.getAllValues().get(1).getContent());
        assertNotNull(cap2.getAllValues().get(1).getCreatedAt());
    }

    @Test
    @DisplayName("emotions/messages：倒序取回后必须反转成正序，且 LIMIT 由入参归一后拼进 SQL")
    void listIsReversedAndLimitNormalized() {
        EmotionRecordMapper em = mock(EmotionRecordMapper.class);
        ChatMessageMapper mm = mock(ChatMessageMapper.class);
        MemoryService svc = new MemoryService(em, mm);

        when(em.selectList(any())).thenReturn(new ArrayList<>(List.of(rec(3), rec(2), rec(1))));
        List<EmotionRecord> out = svc.emotions("s1", 30);
        assertEquals(List.of(1L, 2L, 3L), out.stream().map(EmotionRecord::getId).toList(), "曲线必须时间正序");

        ArgumentCaptor<Wrapper<EmotionRecord>> wc = ArgumentCaptor.forClass(Wrapper.class);
        verify(em).selectList(wc.capture());
        assertTrue(wc.getValue().getSqlSegment().endsWith(" LIMIT 30"),
                "实际 SQL 片段=" + wc.getValue().getSqlSegment());

        when(em.selectList(any())).thenReturn(new ArrayList<>());
        svc.emotions("s1", 0);
        svc.emotions("s1", -5);
        svc.emotions("s1", 9999);
        ArgumentCaptor<Wrapper<EmotionRecord>> wc2 = ArgumentCaptor.forClass(Wrapper.class);
        verify(em, org.mockito.Mockito.times(4)).selectList(wc2.capture());
        List<String> segs = wc2.getAllValues().stream().map(Wrapper::getSqlSegment).toList();
        assertTrue(segs.get(1).endsWith(" LIMIT 200"), "limit=0 应回落 200，实际=" + segs.get(1));
        assertTrue(segs.get(2).endsWith(" LIMIT 200"), "负数 limit 应回落 200，实际=" + segs.get(2));
        assertTrue(segs.get(3).endsWith(" LIMIT 500"), "limit 上限 500 不得被击穿，实际=" + segs.get(3));

        when(mm.selectList(any())).thenReturn(new ArrayList<>(List.of(msg(9), msg(8))));
        List<ChatMessage> mout = svc.messages("s1", 40);
        assertEquals(List.of(8L, 9L), mout.stream().map(ChatMessage::getId).toList());
    }

    @Test
    @DisplayName("clear 回传两张表删除条数之和；stats 的两个计数各自委托对应 mapper")
    void clearAndCounts() {
        EmotionRecordMapper em = mock(EmotionRecordMapper.class);
        ChatMessageMapper mm = mock(ChatMessageMapper.class);
        MemoryService svc = new MemoryService(em, mm);

        when(em.delete(any())).thenReturn(4);
        when(mm.delete(any())).thenReturn(7);
        assertEquals(11, svc.clear("s1"), "清除条数=情绪+消息，只报一张表会让前端以为没清干净");

        when(em.selectCount(any())).thenReturn(4L);
        when(mm.selectCount(any())).thenReturn(7L);
        assertEquals(4L, svc.countEmotions("s1"));
        assertEquals(7L, svc.countMessages("s1"));
    }

    /**
     * 反例守卫（R263 精神）：如果哪天 {@code normLimit} 被改成「原样拼进去」，
     * 上面那条会红；这里再钉一次参照物 —— Wrappers 自己拼 LIMIT 时的形状，
     * 免得判据只是「跟实现一起改」。
     */
    @Test
    @DisplayName("反例参照：同一 last(LIMIT) 写法在 Wrappers 上的形状可被 getSqlSegment 读出")
    void limitFragmentIsReadable() {
        Wrapper<EmotionRecord> w = Wrappers.<EmotionRecord>lambdaQuery()
                .eq(EmotionRecord::getSessionId, "s1")
                .last("LIMIT 200");
        assertTrue(w.getSqlSegment().endsWith(" LIMIT 200"),
                "读不到 LIMIT 说明这条判据本身失效，必须换判据而不是换断言");
    }
}
