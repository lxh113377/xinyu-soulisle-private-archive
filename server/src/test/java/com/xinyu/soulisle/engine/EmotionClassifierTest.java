package com.xinyu.soulisle.engine;

import com.xinyu.soulisle.llm.LlmProxy;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 双路采信判定守卫（r41）。
 *
 * <p>只测**判定链的分支与优先级**，不测上游：用例里的 LlmProxy 一律空 key（离线），
 * 且 crisis 分支刻意给了一个"一被真调用就会失败"的 base，用来证明确实**没走网络**。
 * 上游 JSON 解析那条路要真打 HTTP，属于 {@code _test/j2_chat_contract.py} /
 * {@code engine_consistency_check.py} 的带外面，不在构建期内建。
 */
class EmotionClassifierTest {

    /** 不可达端点：只要有人真去调用它，用例就会以异常/非 200 失败，从而证明"危机不碰上游"。 */
    private static final String DEAD_BASE = "http://127.0.0.1:1/v1";

    private static EmotionClassifier offline() {
        return new EmotionClassifier(new LlmProxy(DEAD_BASE, "deepseek-chat", ""));
    }

    @Test
    @DisplayName("危机优先：path=词典·危机拦截，llm=null，fin=(crisis,1)")
    void crisisTakesTopPriority() {
        EmotionClassifier.Outcome o = offline().classify("感觉活着好累，不想活了");
        assertEquals("词典·危机拦截", o.path());
        assertNull(o.llm(), "危机路径不得调用上游（成本与延迟都不允许）");
        assertNotNull(o.fin());
        assertEquals("crisis", o.fin().emotion());
        assertEquals(1.0, o.fin().intensity(), 1e-9);
        assertTrue(o.lex().crisis());
    }

    @Test
    @DisplayName("离线（无 key）：path=仅词典（离线），fin 与词典层逐项相等")
    void offlineFallsBackToLexicon() {
        EmotionClassifier.Outcome o = offline().classify("论文被拒了三次，心里特别难过");
        assertEquals("仅词典（离线）", o.path());
        assertNull(o.llm());
        assertEquals(o.lex().emotion(), o.fin().emotion());
        assertEquals(o.lex().intensity(), o.fin().intensity(), 1e-9);
        assertEquals("sadness", o.fin().emotion());
    }

    @Test
    @DisplayName("lex 字段永远在（前端双路标签要显示词典读数，哪怕危机或离线）")
    void lexAlwaysPresent() {
        assertNotNull(offline().classify("难过").lex());
        assertNotNull(offline().classify("不想活").lex());
        assertNotNull(offline().classify("").lex());
    }

    @Test
    @DisplayName("空输入不抛：三字段齐、path 走离线")
    void emptyInputSafe() {
        EmotionClassifier.Outcome o = offline().classify("");
        assertEquals("仅词典（离线）", o.path());
        assertEquals("calm", o.fin().emotion());
    }
}
