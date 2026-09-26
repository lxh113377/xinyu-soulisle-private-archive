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

    /** 小工具：避免为本类引入额外断言依赖。 */
    private static void assertArrayEqualsInline(double[] want, double[] got) {
        assertEquals(want.length, got.length);
        for (int i = 0; i < want.length; i++) {
            assertEquals(want[i], got[i], 1e-9);
        }
    }
}
