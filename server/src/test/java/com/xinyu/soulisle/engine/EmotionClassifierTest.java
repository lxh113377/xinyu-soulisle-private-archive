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

    // ------------------------------------------------------------------
    // 三级路由（2026-10-08）：危机短路永不概率化；本地模型高置信采信、低置信升级。
    // 旧双路语义由上面既有用例钉住（兼容构造器 route=lexicon），这里只测新增分支。
    // ------------------------------------------------------------------

    /** 本地模型桩：默认可用、高置信；用 Mockito 便于断言「哪些腿被调用/零调用」 */
    private static ModelProxy modelMock(String emotion, double confidence) {
        ModelProxy m = org.mockito.Mockito.mock(ModelProxy.class);
        org.mockito.Mockito.when(m.enabled()).thenReturn(true);
        org.mockito.Mockito.when(m.classify(org.mockito.ArgumentMatchers.anyString()))
                .thenReturn(new ModelProxy.Verdict(emotion, 0.7, confidence));
        return m;
    }

    private static LlmProxy llmMock(boolean hasKey, String emotion, boolean fail) {
        LlmProxy llm = org.mockito.Mockito.mock(LlmProxy.class);
        org.mockito.Mockito.when(llm.hasKey()).thenReturn(hasKey);
        if (fail) {
            org.mockito.Mockito.when(llm.call(org.mockito.ArgumentMatchers.any(),
                    org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any(),
                    org.mockito.ArgumentMatchers.any()))
                    .thenThrow(new IllegalStateException("upstream down"));
        } else {
            org.mockito.Mockito.when(llm.call(org.mockito.ArgumentMatchers.any(),
                    org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any(),
                    org.mockito.ArgumentMatchers.any()))
                    .thenReturn(new LlmProxy.Result(200, upstreamContent(
                            "{\"emotion\":\"" + emotion + "\",\"intensity\":0.9}")));
        }
        return llm;
    }

    @Test
    @DisplayName("auto+危机短路：本地模型与 LLM 都零调用（安全边界永不概率化）")
    void autoCrisisSkipsBothModels() {
        ModelProxy model = modelMock("sadness", 0.99);
        LlmProxy llm = llmMock(true, "sadness", false);
        EmotionClassifier clf = new EmotionClassifier(llm, model, 8000, "auto");
        EmotionClassifier.Outcome o = clf.classify("感觉活着好累，不想活了");
        assertEquals("词典·危机拦截", o.path());
        assertNull(o.model());
        assertNull(o.llm());
        org.mockito.Mockito.verifyNoInteractions(model, llm);
    }

    @Test
    @DisplayName("auto+词典模型共识：双证据采信，fin 取词典读数，LLM 零调用")
    void autoConsensusUsesLexiconVerdict() {
        // 「明天要答辩，紧张得睡不着」词典读数 = fear ⇒ 模型也回 fear 即共识
        ModelProxy model = modelMock("fear", 0.92);
        LlmProxy llm = llmMock(true, "fear", false);
        EmotionClassifier clf = new EmotionClassifier(llm, model, 8000, "auto");
        EmotionClassifier.Outcome o = clf.classify("明天要答辩，紧张得睡不着");
        assertEquals("词典+模型共识（conf=0.92）", o.path());
        assertEquals("fear", o.fin().emotion());
        assertEquals(o.lex().intensity(), o.fin().intensity(), 1e-9, "共识时强度口径取词典读数");
        assertEquals(0.92, o.model().confidence(), 1e-9, "模型置信度留证据链");
        org.mockito.Mockito.verify(llm, org.mockito.Mockito.never())
                .call(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any(),
                        org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
    }

    @Test
    @DisplayName("auto+分歧：词典裁决不改判，LLM 零调用（在线实测分歧升 LLM 会倒退，已否决）")
    void autoDisagreementAdjudicatedByLexicon() {
        // 词典对这句读数 = sadness ⇒ 模型回 fear 构成分歧
        ModelProxy model = modelMock("fear", 0.55);
        LlmProxy llm = llmMock(true, "sadness", false);
        EmotionClassifier clf = new EmotionClassifier(llm, model, 8000, "auto");
        EmotionClassifier.Outcome o = clf.classify("保研名单里没有我");
        assertEquals("词典与模型分歧 → 词典裁决", o.path());
        assertEquals(o.lex().emotion(), o.fin().emotion(), "分歧时 fin 必须取词典读数");
        assertEquals("fear", o.model().emotion(), "模型腿分歧信号留在证据链里");
        assertNull(o.llm());
        org.mockito.Mockito.verify(llm, org.mockito.Mockito.never())
                .call(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any(),
                        org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
    }

    @Test
    @DisplayName("auto+分歧+离线：同为词典裁决（在线离线行为恒等）")
    void autoDisagreementOfflineSameAsOnline() {
        ModelProxy model = modelMock("love", 0.60);
        LlmProxy llm = llmMock(false, "love", true);
        EmotionClassifier clf = new EmotionClassifier(llm, model, 8000, "auto");
        EmotionClassifier.Outcome o = clf.classify("论文被拒了三次，心里特别难过");
        assertEquals("词典与模型分歧 → 词典裁决", o.path());
        assertEquals("sadness", o.fin().emotion());
        assertNull(o.llm());
    }

    @Test
    @DisplayName("auto+本地模型失败（null）：落回原双路，标签与旧语义逐字一致")
    void autoModelDownFallsBackToLegacy() {
        ModelProxy model = org.mockito.Mockito.mock(ModelProxy.class);
        org.mockito.Mockito.when(model.enabled()).thenReturn(true);
        org.mockito.Mockito.when(model.classify(org.mockito.ArgumentMatchers.anyString()))
                .thenReturn(null);
        // 词典对这句的读数是 sadness ⇒ LLM 回 joy 才触发「分歧」分支
        LlmProxy llm = llmMock(true, "joy", false);
        EmotionClassifier clf = new EmotionClassifier(llm, model, 8000, "auto");
        EmotionClassifier.Outcome o = clf.classify("论文被拒了三次，心里特别难过");
        assertEquals("词典+LLM 分歧 → 采信 LLM", o.path());
        assertNull(o.model(), "本地腿没出结果，model 字段必须为 null");
        assertEquals("joy", o.fin().emotion());
    }

    @Test
    @DisplayName("route=lexicon：本地模型可用也整体关停（演示切换与回归对照）")
    void lexiconRouteDisablesModel() {
        ModelProxy model = modelMock("fear", 0.99);
        LlmProxy llm = llmMock(false, "fear", true);
        EmotionClassifier clf = new EmotionClassifier(llm, model, 8000, "lexicon");
        EmotionClassifier.Outcome o = clf.classify("明天要答辩，紧张得睡不着");
        assertEquals("仅词典（离线）", o.path());
        org.mockito.Mockito.verifyNoInteractions(model);
    }

    @Test
    @DisplayName("兼容构造器（双参）：内部隐含 route=lexicon + 空 ModelProxy ⇒ 行为与引入前逐字节一致")
    void legacyConstructorStaysLexicon() {
        EmotionClassifier clf = new EmotionClassifier(llmMock(false, "fear", true), 8000);
        EmotionClassifier.Outcome o = clf.classify("论文被拒了三次，心里特别难过");
        assertEquals("仅词典（离线）", o.path());
        assertNull(o.model());
        assertNull(o.llm());
    }
}
