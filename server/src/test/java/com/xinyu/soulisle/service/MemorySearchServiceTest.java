package com.xinyu.soulisle.service;

import com.xinyu.soulisle.entity.ChatMessage;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * r128：BM25 长期记忆检索的判据（纯函数，零外部依赖）。
 */
class MemorySearchServiceTest {

    private static ChatMessage msg(long id, String content) {
        ChatMessage m = new ChatMessage();
        m.setId(id);
        m.setSessionId("s1");
        m.setRole("user");
        m.setContent(content);
        return m;
    }

    private static List<ChatMessage> corpus() {
        List<ChatMessage> list = new ArrayList<>();
        list.add(msg(1, "今天考试焦虑得睡不着"));
        list.add(msg(2, "中午吃了拉面，味道还不错"));
        list.add(msg(3, "又要准备期末复习计划"));
        list.add(msg(4, "跟室友聊了聊homework的事情"));
        return list;
    }

    @Test
    @DisplayName("中文能召回语义相近的那条（靠共享 bigram，不靠词典）")
    void findsRelatedChineseMessage() {
        List<MemorySearchService.Hit> hits =
                MemorySearchService.search(corpus(), "复习", 10);
        assertFalse(hits.isEmpty(), "查询「复习」不该零召回");
        assertEquals(3L, hits.get(0).message().getId().longValue(),
                "「又要准备期末复习计划」应排第一");
    }

    @Test
    @DisplayName("「焦虑」召回的是焦虑那条，不是按位置倒序糊弄")
    void findsAnxietyMessage() {
        List<MemorySearchService.Hit> hits =
                MemorySearchService.search(corpus(), "焦虑", 10);
        assertEquals(1, hits.size());
        assertEquals(1L, hits.get(0).message().getId().longValue());
    }

    @Test
    @DisplayName("ASCII 查询小写化后可召回（大小写不敏感）")
    void asciiIsCaseInsensitive() {
        List<MemorySearchService.Hit> upper =
                MemorySearchService.search(corpus(), "HOMEWORK", 10);
        List<MemorySearchService.Hit> lower =
                MemorySearchService.search(corpus(), "homework", 10);
        assertEquals(1, upper.size());
        assertEquals(lower.get(0).message().getId(), upper.get(0).message().getId());
    }

    @Test
    @DisplayName("分值随相关度递减（不是把所有命中的分都写成同一个数）")
    void scoresAreOrdered() {
        List<MemorySearchService.Hit> hits =
                MemorySearchService.search(corpus(), "复习", 10);
        for (int i = 1; i < hits.size(); i++) {
            assertTrue(hits.get(i - 1).score() >= hits.get(i).score(),
                    "分值必须单调不增");
        }
    }

    @Test
    @DisplayName("limit 生效且不为负")
    void limitIsHonored() {
        assertEquals(1, MemorySearchService.search(corpus(), "复习", 1).size());
        assertTrue(MemorySearchService.search(corpus(), "复习", -5).size() <= 10,
                "负 limit 不该产生异常或超大结果集");
    }

    @Test
    @DisplayName("空查询 / 空白查询 / 全停用词一律返回空列表，不抛栈")
    void degenerateQueriesReturnEmpty() {
        assertTrue(MemorySearchService.search(corpus(), null, 10).isEmpty());
        assertTrue(MemorySearchService.search(corpus(), "", 10).isEmpty());
        assertTrue(MemorySearchService.search(corpus(), "   ", 10).isEmpty());
        assertTrue(MemorySearchService.search(corpus(), "完全不相关的量子力学拓扑", 10).isEmpty(),
                "候选集里一个词元都没有时不该硬凑结果");
    }

    @Test
    @DisplayName("空候选集与 null 候选集都返回空列表")
    void emptyCorpusIsSafe() {
        assertTrue(MemorySearchService.search(List.of(), "复习", 10).isEmpty());
        assertTrue(MemorySearchService.search(null, "复习", 10).isEmpty());
    }

    @Test
    @DisplayName("切分口径：CJK 出 bigram，ASCII 出小写单词，标点断词")
    void tokenizationShape() {
        assertTrue(MemorySearchService.vocabulary("今天心情不好")
                .containsAll(List.of("今天", "天心", "心情", "情不", "不好")));
        assertTrue(MemorySearchService.vocabulary("Hello World").contains("hello"));
        assertTrue(MemorySearchService.vocabulary("复习，plan").contains("复习"));
        assertTrue(MemorySearchService.vocabulary("复习，plan").contains("plan"));
    }

    @Test
    @DisplayName("单个汉字不成词元（刻意取舍：宁返空也不给一屏噪声）")
    void singleCjkCharIsNotAToken() {
        assertFalse(MemorySearchService.vocabulary("我").contains("我"));
        assertTrue(MemorySearchService.vocabulary("我").isEmpty());
    }

    @Test
    @DisplayName("同分时按 id 倒序，保证排序可复现（判据要能断言顺序）")
    void tieBreakIsStable() {
        List<ChatMessage> same = new ArrayList<>();
        same.add(msg(7, "重复内容重复内容"));
        same.add(msg(9, "重复内容重复内容"));
        same.add(msg(8, "重复内容重复内容"));
        List<MemorySearchService.Hit> hits =
                MemorySearchService.search(same, "重复内容", 10);
        assertEquals(3, hits.size());
        assertEquals(9L, hits.get(0).message().getId().longValue());
        assertEquals(8L, hits.get(1).message().getId().longValue());
        assertEquals(7L, hits.get(2).message().getId().longValue());
    }

    @Test
    @DisplayName("空内容消息不炸：null/空串消息进候选集仍能算分")
    void blankDocumentsAreSafe() {
        List<ChatMessage> withBlanks = new ArrayList<>();
        withBlanks.add(msg(1, null));
        withBlanks.add(msg(2, ""));
        withBlanks.add(msg(3, "今天心情不好"));
        List<MemorySearchService.Hit> hits =
                MemorySearchService.search(withBlanks, "心情", 10);
        assertEquals(1, hits.size());
        assertEquals(3L, hits.get(0).message().getId().longValue());
    }

    @Test
    @DisplayName("长文档不被 BM25 的长度惩罚吃掉（b=0.75 下 20 倍长度仍有召回）")
    void longDocumentStillMatches() {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 20; i++) {
            sb.append("无关内容填充");
        }
        List<ChatMessage> docs = new ArrayList<>();
        docs.add(msg(1, sb.toString()));
        docs.add(msg(2, "短"));
        List<MemorySearchService.Hit> hits =
                MemorySearchService.search(docs, "无关内容", 10);
        assertEquals(1, hits.size(), "长度惩罚不该把唯一命中的文档压成零召回");
    }
}