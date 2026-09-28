package com.xinyu.soulisle.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xinyu.soulisle.engine.EmotionClassifier;
import com.xinyu.soulisle.llm.LlmProxy;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.http.ResponseEntity;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * {@code POST /api/emotion}、{@code GET /api/emotion/lexicon}、{@code GET /api/emotion/eval} 的行为守卫（r76）。
 *
 * <p>r75 实测本类目标在 0%（117 行未覆盖），而 AC-OBS-09「评测可现场复跑且双端一致」
 * 长期只由 python 判据守着、构建期内零用例。这里把两条最不该漂的结论钉进 JUnit：
 * ① 真实评测集在 Java 侧复跑得 94.4% / 危机 3-3；② 危机词不调上游。
 *
 * <p>形态选择：**直接调用控制器方法**而非 MockMvc——本仓四个控制器都是
 * 「入参 JSON 字符串 → 出 ResponseEntity 字节体」，判定全在方法体内；
 * 直接调用既覆盖全部行，又不把测试结果押在 MVC 装配细节上。
 * 上游一律 Mockito 假对象，构建期内不联网（与 {@code EmotionClassifierTest} 同口径）。
 */
class EmotionControllerTest {

    private static final ObjectMapper M = new ObjectMapper();

    private static String text(ResponseEntity<byte[]> r) {
        return new String(r.getBody(), StandardCharsets.UTF_8);
    }

    /** 离线控制器：hasKey=false ⇒ 分类只走词典 */
    private static EmotionController offline() {
        LlmProxy llm = mock(LlmProxy.class);
        when(llm.hasKey()).thenReturn(false);
        return new EmotionController(new EmotionClassifier(llm, 8000L), "./_test/emotion-eval-dataset.json");
    }

    @Test
    @DisplayName("emotion：干净输入走「仅词典（离线）」，六路结构字段齐备")
    void emotionOffline() throws Exception {
        ResponseEntity<byte[]> r = offline().emotion("{\"text\":\"今天被老师当众骂了一顿，气死我了\"}");
        assertEquals(200, r.getStatusCode().value());
        JsonNode b = M.readTree(text(r));
        assertEquals("仅词典（离线）", b.path("path").asText());
        assertTrue(b.path("llm").isNull(), "离线时 llm 必须是 null，前端据此不画双路证据");
        assertEquals("anger", b.path("final").path("emotion").asText());
        assertTrue(b.path("lex").path("all").isArray() && b.path("lex").path("all").size() > 0);
        assertTrue(b.path("label").asText().length() > 0, "label 由词表单一真相源给出，空即加载器降级");
        assertTrue(b.path("color").isArray() && b.path("color").size() == 3,
                "色值是 SSOT 的三元组 [r,g,b]，不是十六进制串（r76 首跑据此纠正了本用例自己的假设）");
        assertFalse(b.path("lex").path("crisis").asBoolean());
    }

    @Test
    @DisplayName("emotion：危机词短路，上游一次都不被调用")
    void emotionCrisisNeverCallsUpstream() throws Exception {
        LlmProxy llm = mock(LlmProxy.class);
        when(llm.hasKey()).thenReturn(true);
        JsonNode b = M.readTree(text(new EmotionController(new EmotionClassifier(llm, 8000L), "x").emotion(
                "{\"text\":\"我活不下去了，一秒都撑不住\"}")));
        assertEquals("crisis", b.path("final").path("emotion").asText());
        assertTrue(b.path("lex").path("crisis").asBoolean(), "词典层必须自己标出危机，短路才有依据");
        assertEquals("词典·危机拦截", b.path("path").asText());
        assertEquals(1.0, b.path("final").path("intensity").asDouble(), 1e-9);
        verify(llm, never()).call(any(), any(), any(), any(Duration.class));
        verify(llm, never()).hasKey();
    }

    @Test
    @DisplayName("emotion：词典与 LLM 分歧时采信 LLM，一致时标一致")
    void emotionAdoptsLlmOnDivergence() throws Exception {
        JsonNode ok = M.readTree("{\"choices\":[{\"message\":{\"content\":\"{\\\"emotion\\\":\\\"sadness\\\",\\\"intensity\\\":0.75}\"}}]}");
        LlmProxy llm = mock(LlmProxy.class);
        when(llm.hasKey()).thenReturn(true);
        when(llm.call(any(), any(), any(), any(Duration.class))).thenReturn(new LlmProxy.Result(200, ok.toString()));
        JsonNode diverge = M.readTree(text(new EmotionController(new EmotionClassifier(llm, 8000L), "x")
                .emotion("{\"text\":\"今天被老师当众骂了一顿，气死我了\"}")));
        assertEquals("sadness", diverge.path("final").path("emotion").asText());
        assertTrue(diverge.path("path").asText().contains("分歧"), "实际 path=" + diverge.path("path").asText());

        JsonNode agreeBody = M.readTree("{\"choices\":[{\"message\":{\"content\":\"{\\\"emotion\\\":\\\"anger\\\",\\\"intensity\\\":0.66}\"}}]}");
        when(llm.call(any(), any(), any(), any(Duration.class))).thenReturn(new LlmProxy.Result(200, agreeBody.toString()));
        JsonNode agree = M.readTree(text(new EmotionController(new EmotionClassifier(llm, 8000L), "x")
                .emotion("{\"text\":\"今天被老师当众骂了一顿，气死我了\"}")));
        assertTrue(agree.path("path").asText().contains("一致"), "实际 path=" + agree.path("path").asText());
        assertEquals(0.66, agree.path("final").path("intensity").asDouble(), 1e-9);
    }

    @Test
    @DisplayName("emotion：上游报错或给出词表外情绪 ⇒ 回落词典兜底，不抛给前端")
    void emotionFallsBackWhenLlmFails() throws Exception {
        LlmProxy llm = mock(LlmProxy.class);
        when(llm.hasKey()).thenReturn(true);
        when(llm.call(any(), any(), any(), any(Duration.class))).thenReturn(new LlmProxy.Result(502, "{\"error\":\"upstream-error\"}"));
        JsonNode b = M.readTree(text(new EmotionController(new EmotionClassifier(llm, 8000L), "x")
                .emotion("{\"text\":\"今天被老师当众骂了一顿，气死我了\"}")));
        assertEquals("LLM 精判失败 → 词典兜底", b.path("path").asText());
        assertEquals("anger", b.path("final").path("emotion").asText());

        JsonNode junk = M.readTree("{\"choices\":[{\"message\":{\"content\":\"{\\\"emotion\\\":\\\"envy\\\",\\\"intensity\\\":0.9}\"}}]}");
        when(llm.call(any(), any(), any(), any(Duration.class))).thenReturn(new LlmProxy.Result(200, junk.toString()));
        JsonNode b2 = M.readTree(text(new EmotionController(new EmotionClassifier(llm, 8000L), "x")
                .emotion("{\"text\":\"今天被老师当众骂了一顿，气死我了\"}")));
        assertEquals("LLM 精判失败 → 词典兜底", b2.path("path").asText());
    }

    @Test
    @DisplayName("emotion：空体/坏 JSON/非对象/缺 text 四种输入一律 400 bad-json，绝不 500")
    void emotionRejectsMalformedBody() {
        EmotionController c = offline();
        assertEquals(400, c.emotion(null).getStatusCode().value());
        assertEquals(400, c.emotion("").getStatusCode().value());
        assertEquals(400, c.emotion("{oops").getStatusCode().value());
        assertEquals(400, c.emotion("[1,2]").getStatusCode().value());
        assertEquals(400, c.emotion("{\"noText\":\"x\"}").getStatusCode().value());
        assertEquals("{\"error\":\"bad-json\"}", text(c.emotion("{oops")));
    }

    @Test
    @DisplayName("lexicon：导出的是单一真相源那份结构；危机词表与护栏词表是两套，不得互相冒充")
    void lexiconExportMatchesSsot() throws Exception {
        JsonNode b = M.readTree(text(offline().lexicon()));
        for (String k : new String[] {"lex", "neg", "deg", "crisis"}) {
            assertTrue(b.has(k), "缺字段 " + k);
        }
        for (String e : new String[] {"joy", "sadness", "anger", "fear", "calm", "love"}) {
            JsonNode c = b.path("lex").path(e);
            assertTrue(c.isObject(), "词典缺情绪 " + e);
            assertTrue(c.path("weight").isNumber(), e + " 缺 weight");
            assertEquals(3, c.path("color").size(), e + " 的色值必须是 [r,g,b] 三元组");
            assertTrue(c.path("words").size() > 0, e + " 词表为空 ⇒ 加载器静默吞掉了内容");
        }
        assertTrue(b.path("crisis").isArray() && b.path("crisis").size() > 0,
                "危机词是顶层独立数组，与 lex 六情绪并列，不在 lex 内");
        // 与 SSOT **逐元素**比（不比文件原文子串：Jackson 序列化不留逗号后的空格，那是格式不是内容）
        String ssot = Files.readString(Path.of("src", "data", "emotion-lexicon.js"), StandardCharsets.UTF_8);
        // 锚点必须带赋值号：SSOT 的**注释里**同时出现过 `${XINYU_LEXICON}`（带花括号）
        // 和 `（经 window.__XINYU_LEXICON__）`（裸标记）——两条都能把定位带偏，
        // 这正是 EmotionLexicon.java:117-119 自己记下的坑，本用例首跑当场复现了第②条。
        int mark = ssot.indexOf("__XINYU_LEXICON__ =");
        assertTrue(mark >= 0, "SSOT 文件少了全局赋值锚点");
        int open = ssot.indexOf('{', mark);
        JsonNode src = M.readTree(ssot.substring(open, ssot.lastIndexOf('}') + 1));
        assertEquals(src.path("lex").path("joy").path("words"), b.path("lex").path("joy").path("words"),
                "joy 词表逐元素不等 ⇒ Java 加载器改了顺序或内容（键顺序与重复项都是有意义的）");
        assertEquals(src.path("crisis"), b.path("crisis"), "危机词表与 SSOT 不等");
        assertTrue(src.path("crisis").toString().contains("轻生"), "危机词表须真从 SSOT 载入");
        assertFalse(b.path("crisis").toString().contains("跳楼"),
                "「跳楼」属 SafetyGuard 的输出高危词，不在词典危机词表内 —— 两套词表边界不得互相冒充（r76 首跑实测）");
    }

    /**
     * r76 首跑就把一条挂了三轮的过期断言打了出来：AGENTS.md 的 AC-OBS-09 与 J3 行仍写
     * 「36 条 / 94.4% / crisis 3-3 / misses 两条」，而磁盘现值是 <b>73 条 / 98.6% / crisis 6-6 / misses 一条</b>
     * （评测集 09-23 由 36 扩到 73，标题数字没人重算）。这里按**当场实测**取值，并同步把文档更正到位。
     */
    @Test
    @DisplayName("eval：真实评测集在 Java 侧复跑 = 73 条 / 98.6% / 危机 6-6（AC-OBS-09 的构建期锁）")
    void evalOnRealDataset() throws Exception {
        ResponseEntity<byte[]> r = offline().eval(0);
        assertEquals(200, r.getStatusCode().value());
        JsonNode b = M.readTree(text(r));
        assertEquals(73, b.path("total").asInt());
        assertEquals("98.6%", b.path("accuracy").asText());
        assertEquals("6/6", b.path("crisis_recall").asText());
        assertEquals(1, b.path("misses").size(), "漏判数变了就必须同步双端对账判据，不许默默漂");
    }

    @Test
    @DisplayName("eval：detail=1 才逐条回传，条数恒等于 total（供逐条比对而非只看汇总）")
    void evalDetailReturnsEveryRow() throws Exception {
        JsonNode b = M.readTree(text(offline().eval(1)));
        assertEquals(b.path("total").asInt(), b.path("results").size());
        JsonNode first = b.path("results").get(0);
        for (String k : new String[] {"text", "expect", "pred"}) {
            assertTrue(first.has(k), "逐条行缺字段 " + k);
        }
        assertEquals("98.6%", b.path("accuracy").asText());
    }

    @Test
    @DisplayName("eval：路径不存在 404、非法 JSON 500、items 空 500 —— 三种失败各自可辨且路径含反斜杠仍是合法 JSON")
    void evalFailureBranches(@TempDir Path tmp) throws Exception {
        Path missing = tmp.resolve("nope/does-not-exist.json");
        ResponseEntity<byte[]> r404 = new EmotionController(new EmotionClassifier(mock(LlmProxy.class), 8000L),
                missing.toString()).eval(0);
        assertEquals(404, r404.getStatusCode().value());
        JsonNode b404 = M.readTree(text(r404));
        assertEquals("dataset-not-found", b404.path("error").asText());
        assertTrue(b404.path("path").asText().length() > 0, "回传的绝对路径必须能解析成合法 JSON");

        Path broken = tmp.resolve("broken.json");
        Files.write(broken, "{ 这不是 JSON".getBytes(StandardCharsets.UTF_8));
        assertEquals(500, new EmotionController(new EmotionClassifier(mock(LlmProxy.class), 8000L),
                broken.toString()).eval(0).getStatusCode().value());

        Path empty = tmp.resolve("empty.json");
        Files.write(empty, "{\"items\":[]}".getBytes(StandardCharsets.UTF_8));
        assertEquals(500, new EmotionController(new EmotionClassifier(mock(LlmProxy.class), 8000L),
                empty.toString()).eval(0).getStatusCode().value());
    }

    @Test
    @DisplayName("eval：全错样本的算术必须自洽 —— accuracy/per_class/misses 三处同源自同一批判定")
    void evalArithmeticIsSelfConsistent(@TempDir Path tmp) throws Exception {
        Path ds = tmp.resolve("all-wrong.json");
        Files.write(ds, ("{\"items\":["
                + "{\"text\":\"甲\",\"expect\":\"qqq\"},"
                + "{\"text\":\"乙\",\"expect\":\"qqq\"},"
                + "{\"text\":\"丙\",\"expect\":\"www\"}]}").getBytes(StandardCharsets.UTF_8));
        JsonNode b = M.readTree(text(new EmotionController(new EmotionClassifier(mock(LlmProxy.class), 8000L),
                ds.toString()).eval(0)));
        assertEquals(3, b.path("total").asInt());
        assertEquals("0.0%", b.path("accuracy").asText());
        assertEquals("0/2", b.path("per_class").path("qqq").asText());
        assertEquals("0/1", b.path("per_class").path("www").asText());
        assertEquals(3, b.path("misses").size());
        assertEquals("0/0", b.path("crisis_recall").asText());
    }
}
