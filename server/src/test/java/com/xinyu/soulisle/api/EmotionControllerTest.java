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
 * <p>r112 更正：评测集 73 → 79 条（+4 条远距离否定「没什么好/可 + 情绪词」、+2 条防扩窗误伤对抗），
 * 且否定取词窗口 3 → 4（配「否定词与情绪词之间隔标点则不生效」的断点规则），
 * 双端同时生效后准确率 98.6% → <b>100.0%</b>、漏判 1 → 0。本锁的价值正在于此：
 * 评测集一动，构建期立刻红，逼着人去核对双端而不是让数字默默漂。
 * （注：Java 侧格式化是「100.0%」一位小数，JS 侧是「100%」，格式不同非分叉。）
 *
 * <p>⚠️ r168 更正上一段那句「评测集一动，构建期立刻红」：<b>会红不等于该红</b>。断言里钉的是
 * 写下那行代码当天的快照，于是扩充评测集（85 → 105，并带入 1 条真实漏判）后，这两条断言
 * 在 HEAD 面<b>恒红</b>（实测 {@code mvn test} Failures: 2，CI 的 java-build 步跟着一起红），
 * 而它红的原因不是引擎退化 —— 属本仓 r98 立的「验收标准按构造不可达」族。
 * 现改为「期望值由同一份评测文件与逐条读数当场重算」：扩充永不致红，
 * 而①危机漏判、②汇总与明细不自洽这两件真缺陷仍然会红（本类 docstring 与用例注释各留一份口径，
 * 以用例注释为执行面）。上面两段历史数字（94.4% / 3-3 / 79 条 / 100.0%）按其当日为真保留，不再作为断言依据。
 *
 * <p>形态选择：**直接调用控制器方法**而非 MockMvc——本仓四个控制器都是
 * 「入参 JSON 字符串 → 出 ResponseEntity 字节体」，判定全在方法体内；
 * 直接调用既覆盖全部行，又不把测试结果押在 MVC 装配细节上。
 * 上游一律 Mockito 假对象，构建期内不联网（与 {@code EmotionClassifierTest} 同口径）。
 */
class EmotionControllerTest {

    private static final ObjectMapper M = new ObjectMapper();

    private static final String EVAL_PATH = "./_test/emotion-eval-dataset.json";

    private static String text(ResponseEntity<byte[]> r) {
        return new String(r.getBody(), StandardCharsets.UTF_8);
    }

    /** 离线控制器：hasKey=false ⇒ 分类只走词典 */
    private static EmotionController offline() {
        LlmProxy llm = mock(LlmProxy.class);
        when(llm.hasKey()).thenReturn(false);
        return new EmotionController(new EmotionClassifier(llm, 8000L), EVAL_PATH);
    }

    /**
     * 评测集取数面：<b>与被审对象用同一条路径字符串</b>，这样「期望值由文件现读」不依赖
     * 构建目录恰好是项目根还是模块根（r130 §8 教训 2 的同一条相对路径坑，换个方向再咬一次）。
     */
    private static JsonNode datasetItems() throws Exception {
        JsonNode root = M.readTree(new String(java.nio.file.Files.readAllBytes(java.nio.file.Path.of(EVAL_PATH)),
                StandardCharsets.UTF_8));
        JsonNode items = root.path("items");
        assertTrue(items.isArray() && !items.isEmpty(),
                "评测集取不到 items ⇒ 本类的对账全部失去分母，不得静默当通过");
        return items;
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
     *
     * <p>⚠️ r168 更正本用例自己的做法：<b>「按当场实测取值」仍然是抄快照</b> —— 抄的是写下那行代码当天的值。
     * 评测集 09-29 起又从 85 扩到 105 条（并带入 1 条真实漏判），于是这两条断言自那次扩充起
     * <b>在 HEAD 面恒红</b>（{@code mvn test} 实测 Failures: 2，CI 的 java-build 步跟着一起红），
     * 而任何一次扩充都会再红一次 ⇒ 属本仓 r98 立的「验收标准按构造不可达」族。
     * 正解不是把 85 改成 105、把 100.0% 改成 99.0%（那是再抄一次），而是让期望值
     * <b>由同一份评测文件与逐条读数当场重算</b>：条数取自文件、危机分母取自文件、
     * 准确率由 results 反推、misses 数由 total-correct 反推。这样扩充评测集永不致红，
     * 而真正会红的两件事留住了：① 危机漏判（分子≠分母）；② 汇总口径与逐条读数不自洽。
     */
    @Test
    @DisplayName("eval：真实评测集在 Java 侧复跑 —— 期望值当场由数据集与逐条读数重算，不抄快照（AC-OBS-09 构建期锁）")
    void evalOnRealDataset() throws Exception {
        JsonNode items = datasetItems();
        JsonNode b = M.readTree(text(offline().eval(1)));

        assertEquals(items.size(), b.path("total").asInt(),
                "total 必须等于同一份评测文件的现读条数（两端读的是同一个文件，见决策 #5）");

        int crisisRows = 0;
        for (JsonNode it : items) {
            if ("crisis".equals(it.path("expect").asText())) {
                crisisRows++;
            }
        }
        String[] recall = b.path("crisis_recall").asText().split("/");
        assertEquals(crisisRows, Integer.parseInt(recall[1]),
                "crisis_recall 的分母必须等于数据集里 expect=crisis 的条数（现读，不抄）");
        assertEquals(recall[1], recall[0],
                "危机一条都不许漏 —— 这条与条数无关，扩充评测集也不该让它红");

        int correct = 0;
        for (JsonNode row : b.path("results")) {
            if (row.path("expect").asText().equals(row.path("pred").asText())) {
                correct++;
            }
        }
        assertEquals(Math.round(correct * 1000.0 / b.path("total").asInt()) / 10.0 + "%",
                b.path("accuracy").asText(), "汇总准确率必须等于逐条读数重算值（防只改汇总不改明细）");
        assertEquals(b.path("total").asInt() - correct, b.path("misses").size(),
                "misses 条数必须等于 total 减逐条命中数");
        for (JsonNode miss : b.path("misses")) {
            for (String k : new String[] {"text", "expect", "pred"}) {
                assertTrue(miss.has(k), "每条漏判都得带齐双端对账要用的三件，缺一则 misses 无法复核");
            }
        }
    }

    @Test
    @DisplayName("eval：detail=1 才逐条回传，条数恒等于 total（供逐条比对而非只看汇总）")
    void evalDetailReturnsEveryRow() throws Exception {
        JsonNode b = M.readTree(text(offline().eval(1)));
        assertEquals(b.path("total").asInt(), b.path("results").size());
        assertEquals(datasetItems().size(), b.path("results").size(),
                "逐条行数必须与数据集现读条数一一对应（r168：原断言在此处抄了 100.0% 快照，已换成现读对账）");
        JsonNode first = b.path("results").get(0);
        for (String k : new String[] {"text", "expect", "pred"}) {
            assertTrue(first.has(k), "逐条行缺字段 " + k);
        }
        assertFalse(b.path("results").get(0).path("text").asText().isEmpty(), "明细里文本不得被抹空");
        // detail=0 那一半分支也得有人走：汇总在、明细缺席（前端只要读数时不背 105 行）
        JsonNode z = M.readTree(text(offline().eval(0)));
        assertTrue(z.has("accuracy") && z.has("misses"), "detail=0 仍须给出汇总与漏判");
        assertFalse(z.has("results"), "detail=0 却把逐条行也塞回来 ⇒ 响应体会随评测集规模线性膨胀");
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

        // items 根本不是数组（写成对象）：与空数组同一出口，不许当成「零条样本」跑出 accuracy=NaN
        Path shaped = tmp.resolve("items-object.json");
        Files.write(shaped, "{\"items\":{\"1\":\"x\"}}".getBytes(StandardCharsets.UTF_8));
        ResponseEntity<byte[]> objResp = new EmotionController(
                new EmotionClassifier(mock(LlmProxy.class), 8000L), shaped.toString()).eval(0);
        assertEquals(500, objResp.getStatusCode().value());
        assertEquals("dataset-empty", M.readTree(text(objResp)).path("error").asText(),
                "items 写成对象要与空数组同出口，不许跑出 accuracy=NaN");
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

    @Test
    @DisplayName("r77 危机召回要能记「漏」：同批里命中与未命中各一条 ⇒ 1/2，不许只统计命中")
    void crisisRecallCountsMissesToo(@TempDir Path tmp) throws Exception {
        Path ds = tmp.resolve("crisis-mixed.json");
        Files.write(ds, ("{\"items\":["
                + "{\"text\":\"感觉活着好累，不想活了\",\"expect\":\"crisis\"},"
                + "{\"text\":\"今天天气不错\",\"expect\":\"crisis\"}"
                + "]}").getBytes(StandardCharsets.UTF_8));
        JsonNode b = M.readTree(text(controllerAt(ds.toString()).eval(0)));
        assertEquals("1/2", b.path("crisis_recall").asText(),
                "危机漏报必须进分母：只报命中数会把安全边界读成满分");
        assertEquals(1, b.path("misses").size());
    }

    @Test
    @DisplayName("r77 emotion 入参形状：text 为 null 与顶层非对象都是 400（不得拿空串走词典）")
    void emotionRejectsNonTextShapes() throws Exception {
        assertEquals(400, offline().emotion("{\"text\":null}").getStatusCode().value());
        assertEquals(400, offline().emotion("[{\"text\":\"难过\"}]").getStatusCode().value());
        assertEquals(400, offline().emotion("null").getStatusCode().value());
    }

    private static EmotionController controllerAt(String dataset) {
        return new EmotionController(new EmotionClassifier(mock(LlmProxy.class), 8000L), dataset);
    }
}
