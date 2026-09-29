package com.xinyu.soulisle.engine;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 词表单一真相源（SSOT）加载守卫（r41）。
 *
 * <p>这一组用例顺带钉住一条此前**只由"跑起来才知道"支撑**的隐含前提：
 * {@code EmotionLexicon} 默认按 {@code ./src/} 解析，而 surefire 的 workingDirectory
 * 已被 pom 指到仓库根 ⇒ 构建期能加载成功，就等价于「工作目录=项目根」这条铁律成立。
 * 加载失败会让本类**全部**用例抛 IllegalStateException 而红，不会静默跳过。
 */
class EmotionLexiconTest {

    @Test
    @DisplayName("SSOT 已加载且非空：六情绪 + 危机词 + 否定词 + 程度词全在")
    void ssotLoaded() {
        assertNotNull(EmotionLexicon.LEXICON_PATH);
        assertEquals(6, EmotionLexicon.LEX.size(), "情绪类数须与前端 SSOT 一致（joy/sadness/anger/fear/calm/love）");
        assertFalse(EmotionLexicon.CRISIS.isEmpty(), "危机词表为空 = 安全边界失效");
        assertFalse(EmotionLexicon.NEG.isEmpty());
        assertFalse(EmotionLexicon.DEG.isEmpty());
        assertTrue(EmotionLexicon.LEXICON_PATH.endsWith("data/emotion-lexicon.js"),
                "解析结果须指向前端权威源，实际=" + EmotionLexicon.LEXICON_PATH);
    }

    @Test
    @DisplayName("EMOTIONS 顺序 == LEX 插入序（平分兜底顺序必须与 JS 一致）")
    void emotionOrderMatchesInsertion() {
        assertEquals(new ArrayList<>(EmotionLexicon.LEX.keySet()), EmotionLexicon.EMOTIONS);
        assertEquals("joy", EmotionLexicon.EMOTIONS.get(0), "JS 端 joy 是第一个键");
    }

    @Test
    @DisplayName("每个情绪：色值 3 分量、权重在 (0,1]、词表非空")
    void cfgShape() {
        for (String emo : EmotionLexicon.EMOTIONS) {
            EmotionLexicon.Cfg cfg = EmotionLexicon.LEX.get(emo);
            assertEquals(3, cfg.color().length, emo + " 色值须 3 分量");
            assertTrue(cfg.weight() > 0 && cfg.weight() <= 1, emo + " 权重越界: " + cfg.weight());
            assertFalse(cfg.words().isEmpty(), emo + " 词表为空");
        }
        assertEquals(3, EmotionLexicon.CRISIS_COLOR.length);
    }

    @Test
    @DisplayName("重复词必须原样保留：它们参与计分，顺手去重会直接改变分数")
    void duplicatesArePreservedNotDeduped() {
        // 本用例首跑就是这条**红**的 —— 我原先断言"情绪内不得有重复词"，那是我的假设，
        // 不是事实：SSOT 里 sadness 的「难受」与 neg 的「不」都是**故意重复**的，
        // 加载器必须照单全收（去重 = 改分数）。见 _test/engine_consistency_check.py 判据 A 的注记。
        // 现在反过来钉住它：一旦有人"顺手去重"（改数据或改加载器），这里立刻红。
        java.util.Map<String, Integer> seen = new java.util.LinkedHashMap<>();
        int dupTotal = 0;
        for (String emo : EmotionLexicon.EMOTIONS) {
            seen.clear();
            for (String w : EmotionLexicon.LEX.get(emo).words()) {
                seen.merge(w, 1, Integer::sum);
            }
            dupTotal += (int) seen.values().stream().filter(c -> c > 1).count();
        }
        assertTrue(dupTotal > 0, "词表里的重复项被去掉了（会改变分数）：重复项数=" + dupTotal);
        long negDup = EmotionLexicon.NEG.stream().distinct().count();
        assertTrue(EmotionLexicon.NEG.size() > negDup,
                "否定词的重复项（「不」出现两次）被去掉了 ⇒ 与 JS 端不再同构");
    }

    @Test
    @DisplayName("标签回落：未知情绪给 平静，crisis 有专属标签")
    void labelFallback() {
        assertEquals("平静", EmotionLexicon.labelOf("no-such-emotion"));
        assertEquals("危机信号", EmotionLexicon.labelOf("crisis"));
        assertEquals("低落", EmotionLexicon.labelOf("sadness"));
    }

    @Test
    @DisplayName("colorOf 三态：crisis 走危机色、未知情绪回落 calm、且返回副本不得改到常量")
    void colorOfBehavior() {
        double[] crisis = EmotionLexicon.colorOf("crisis");
        assertArrayEqualsInline(EmotionLexicon.CRISIS_COLOR, crisis);
        double[] calm = EmotionLexicon.colorOf("calm");
        assertArrayEqualsInline(EmotionLexicon.LEX.get("calm").color(), EmotionLexicon.colorOf("???"));
        calm[0] = 0.999;
        assertEquals(0.25, EmotionLexicon.LEX.get("calm").color()[0],
                "colorOf 必须给副本：改返回值不得污染 LEX 常量");
    }

    /**
     * r77：路径解析的三条优先级此前只有真起进程才验得到，而 fat jar（工作目录=项目根）
     * 与 Docker（XINYU_WEB_ROOT=/app/web）走的正好是不同腿。
     */
    @Test
    @DisplayName("resolvePath 三态：显式路径 > web root（剥尾斜杠）> 默认 ./src/，空白串按「没设」处理")
    void resolvePathPriority() {
        assertEquals("/etc/my-lex.js", EmotionLexicon.resolvePath("/etc/my-lex.js", "/app/web"));
        assertEquals("./src/data/emotion-lexicon.js", EmotionLexicon.resolvePath(null, null),
                "两个环境变量都没设 ⇒ 默认命中前端权威源");
        assertEquals("./src/data/emotion-lexicon.js", EmotionLexicon.resolvePath("   ", "  "),
                "空串/纯空白等于没设（否则启动会去找一个不存在的路径）");
        assertEquals("/app/web/data/emotion-lexicon.js", EmotionLexicon.resolvePath("", "/app/web/"));
        assertEquals("src/data/emotion-lexicon.js", EmotionLexicon.resolvePath(null, "src///"),
                "多重尾斜杠一次剥干净");
    }

    @Test
    @DisplayName("SSOT 定位的四种坏形态都要 fail-fast，且报错点名文件（不许静默回退到旧词表）")
    void readLexiconFailFast() throws Exception {
        java.nio.file.Path dir = java.nio.file.Files.createTempDirectory("xinyu-lex-fixture");
        assertTrue(EmotionLexicon.readLexicon(EmotionLexicon.LEXICON_PATH).path("lex").size() >= 6,
                "真源先自证读得动（否则下面的坏形态红因会分不清）");

        assertLoadFails(dir.resolve("no-marker.js"), "window.__NOTHING__ = {\"lex\":{}};", "没有标记");
        assertLoadFails(dir.resolve("no-brace.js"), "window.__XINYU_LEXICON__ = 42;", "标记后面没有 JSON 左括号");
        assertLoadFails(dir.resolve("unbalanced.js"), "window.__XINYU_LEXICON__ = {\"lex\":{}", "只有左括号没有右括号");
        assertLoadFails(dir.resolve("missing-file.js"), null, "文件根本不存在");
    }

    @Test
    @DisplayName("r83 补形：右括号在左括号之前才算「定位失败」，旧用例那条其实走的是解析异常")
    void readLexiconBraceOrderReversed() throws Exception {
        // 逐行复算发现的形态差：`{ 与 }` 都存在且 } 在 { 之后时，e<=s 为假，
        // 旧 unbalanced.js 的 `{"lex":{}` 末尾自带 } ⇒ 它其实是被 Jackson 解析失败抓住的，
        // guard 的 e<=s 那一支从未真取过 ⇒ 定位守卫的失败面长期没人走。
        java.nio.file.Path dir = java.nio.file.Files.createTempDirectory("xinyu-lex-order");
        assertLoadFails(dir.resolve("reversed.js"), "{\"a\":1} window.__XINYU_LEXICON__ = {\"lex\":{\"joy\":[]",
                "最后一个右括号落在第一个左括号之前");
        assertLoadFails(dir.resolve("no-close.js"), "window.__XINYU_LEXICON__ = {\"lex\":{\"joy\":[]",
                "全文没有任何右括号（e=-1 同样该落进 e<=s）");
    }

    private static void assertLoadFails(java.nio.file.Path p, String content, String why) throws Exception {
        if (content != null) {
            java.nio.file.Files.writeString(p, content, java.nio.charset.StandardCharsets.UTF_8);
        }
        IllegalStateException ex = org.junit.jupiter.api.Assertions.assertThrows(IllegalStateException.class,
                () -> EmotionLexicon.readLexicon(p.toString()), why + " 时必须抛，实际静默通过");
        assertTrue(ex.getMessage().contains(p.getFileName().toString()),
                why + " ⇒ 报错要点名是哪个文件坏了，实际=" + ex.getMessage());
    }

    @Test
    @DisplayName("注释里的花括号与标记都不得带偏定位（真源里两种坑都写过的回归锁）")
    void readLexiconIgnoresComments() throws Exception {
        java.nio.file.Path p = java.nio.file.Files.createTempDirectory("xinyu-lex-ok").resolve("lex.js");
        java.nio.file.Files.writeString(p, "/* 见 ${XINYU_LEXICON} 与（经 window.__XINYU_LEXICON__）*/\n"
                + "// window.__XINYU_LEXICON__ 也出现在行注释里 {\"bogus\":true}\n"
                + "window.__XINYU_LEXICON__ = {\"lex\":{\"joy\":{\"weight\":0.9,\"color\":[0,1,0],\"words\":[\"哈\"]}}};\n",
                java.nio.charset.StandardCharsets.UTF_8);
        com.fasterxml.jackson.databind.JsonNode root = EmotionLexicon.readLexicon(p.toString());
        assertEquals(1, root.size(), "只许取到那条真语句的字面量");
        assertEquals(1, root.path("lex").size());
        assertFalse(root.has("bogus"), "行注释里的假 JSON 不得被当成词表");
    }

    @Test
    @DisplayName("toStringList：null 给空表（SSOT 少一个键不得 NPE），非 null 逐项转文本")
    void toStringListShapes() {
        assertTrue(EmotionLexicon.toStringList(null).isEmpty());
        assertEquals(List.of("活不下去", "想不开"),
                EmotionLexicon.toStringList(
                        new com.fasterxml.jackson.databind.ObjectMapper().createArrayNode()
                                .add("活不下去").add("想不开")));
    }

    /** 小工具：避免为本类引入额外断言依赖。 */
    private static void assertArrayEqualsInline(double[] want, double[] got) {
        assertEquals(want.length, got.length);
        for (int i = 0; i < want.length; i++) {
            assertEquals(want[i], got[i], 1e-9);
        }
    }
}
