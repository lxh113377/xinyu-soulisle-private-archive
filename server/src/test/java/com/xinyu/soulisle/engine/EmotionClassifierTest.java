package com.xinyu.soulisle.engine;

import com.xinyu.soulisle.llm.LlmProxy;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

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

    /**
     * r70：分类腿的超时预算必须真的生效 —— 上游「accept 后一个字节都不回」时，
     * 整条 classify 要在**短预算**内回落词典，而不是占着线程等满 60s。
     *
     * <p>用 2s 预算跑，判据取「&lt;6s」而不是「≈2s」：本机调度抖动不该把守卫跑成 flake，
     * 但 60s 那条旧路径一定越不过 6s ⇒ 这一档足以区分修前/修后。
     */
    @Test
    @DisplayName("挂起上游：classify 在超时预算内回落词典（path=LLM 精判失败 → 词典兜底）")
    void hangingUpstreamDegradesWithinBudget() throws Exception {
        try (ServerSocket blackHole = new ServerSocket(0, 16, InetAddress.getLoopbackAddress())) {
            AtomicInteger accepted = new AtomicInteger();
            List<Socket> held = Collections.synchronizedList(new ArrayList<>());
            Thread sink = new Thread(() -> {
                while (!blackHole.isClosed()) {
                    try {
                        Socket s = blackHole.accept();
                        held.add(s);
                        accepted.incrementAndGet();
                    } catch (IOException e) {
                        return;
                    }
                }
            });
            sink.setDaemon(true);
            sink.start();

            String base = "http://127.0.0.1:" + blackHole.getLocalPort() + "/v1";
            LlmProxy proxy = new LlmProxy(base, "deepseek-chat", "test-key-not-a-real-secret");
            EmotionClassifier clf = new EmotionClassifier(proxy, 2000);

            long t0 = System.nanoTime();
            EmotionClassifier.Outcome o = clf.classify("论文被拒了三次，心里特别难过");
            double elapsed = (System.nanoTime() - t0) / 1e9;

            assertEquals("LLM 精判失败 → 词典兜底", o.path(), "挂起必须走兜底，而不是把异常抛给调用方");
            assertEquals("sadness", o.fin().emotion(), "兜底结果仍须是词典读数");
            assertNull(o.llm());
            assertTrue(accepted.get() >= 1, "对端确实接了这条连接（否则测的是拒连而不是挂起）");
            assertTrue(elapsed < 6.0, "超时预算未生效：实测 " + elapsed + "s");
            held.forEach(s -> {
                try {
                    s.close();
                } catch (IOException ignored) {
                    // 回收失败不影响判据
                }
            });
        }
    }

    @Test
    @DisplayName("危机词在任何配置下都不碰上游（连 socket 都不该建）")
    void crisisNeverTouchesNetworkEvenWithKey() throws Exception {
        try (ServerSocket blackHole = new ServerSocket(0, 16, InetAddress.getLoopbackAddress())) {
            AtomicInteger accepted = new AtomicInteger();
            Thread sink = new Thread(() -> {
                while (!blackHole.isClosed()) {
                    try {
                        Socket s = blackHole.accept();
                        accepted.incrementAndGet();
                        s.close();
                    } catch (IOException e) {
                        return;
                    }
                }
            });
            sink.setDaemon(true);
            sink.start();
            String base = "http://127.0.0.1:" + blackHole.getLocalPort() + "/v1";
            EmotionClassifier clf = new EmotionClassifier(
                    new LlmProxy(base, "deepseek-chat", "test-key-not-a-real-secret"), 2000);
            EmotionClassifier.Outcome o = clf.classify("感觉活着好累，不想活了");
            assertEquals("词典·危机拦截", o.path());
            assertEquals(0, accepted.get(), "危机路径不得建任何连接");
        }
    }

    /** 上游回体的最小形状：只有 content 是我们在意的 */
    private static String upstreamContent(String content) {
        return "{\"choices\":[{\"message\":{\"content\":"
                + com.fasterxml.jackson.databind.node.JsonNodeFactory.instance.textNode(content) + "}}]}";
    }

    @Test
    @DisplayName("r77 LLM 精判的三形坏回复：没 JSON / 情绪名不在枚举 / intensity 不是数字，前两者整腿回落词典")
    void malformedLlmReplies() {
        com.xinyu.soulisle.llm.LlmProxy llm =
                org.mockito.Mockito.mock(com.xinyu.soulisle.llm.LlmProxy.class);
        org.mockito.Mockito.when(llm.hasKey()).thenReturn(true);
        org.mockito.Mockito.when(llm.call(org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any()))
                .thenReturn(new LlmProxy.Result(200, upstreamContent("我看不太懂你在说什么")));
        EmotionClassifier clf = new EmotionClassifier(llm, 2000);

        EmotionClassifier.Outcome noJson = clf.classify("论文被拒了三次，心里特别难过");
        assertEquals("LLM 精判失败 → 词典兜底", noJson.path(), "回复里没有花括号 ⇒ 整腿作废");
        org.junit.jupiter.api.Assertions.assertNull(noJson.llm());
        assertEquals("sadness", noJson.fin().emotion());

        org.mockito.Mockito.when(llm.call(org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any()))
                .thenReturn(new LlmProxy.Result(200, upstreamContent("{\"emotion\":\"狂喜\",\"intensity\":0.9}")));
        EmotionClassifier.Outcome badEmotion = clf.classify("论文被拒了三次，心里特别难过");
        assertEquals("LLM 精判失败 → 词典兜底", badEmotion.path(), "情绪名不在六类枚举内不得采信");
        assertEquals("sadness", badEmotion.fin().emotion());

        // intensity 非数字 / 缺失：这一腿**仍算成功**（情绪名有效），只是强度按 0.5 中值，不许拿词典分数冒充 LLM 分数
        org.mockito.Mockito.when(llm.call(org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any()))
                .thenReturn(new LlmProxy.Result(200, upstreamContent("{\"emotion\":\"joy\",\"intensity\":\"很高\"}")));
        EmotionClassifier.Outcome strIntensity = clf.classify("论文被拒了三次，心里特别难过");
        assertEquals("joy", strIntensity.fin().emotion(), "词典与 LLM 分歧时仍采信 LLM");
        assertEquals(0.5, strIntensity.fin().intensity(), 1e-9, "intensity 不是数字 ⇒ 取 0.5 中值");

        org.mockito.Mockito.when(llm.call(org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any()))
                .thenReturn(new LlmProxy.Result(200, upstreamContent("{\"emotion\":\"calm\"}")));
        assertEquals(0.5, clf.classify("今天天气不错").fin().intensity(), 1e-9, "intensity 缺失同样取 0.5");
    }
}
