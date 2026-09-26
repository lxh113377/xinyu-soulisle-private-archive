package com.xinyu.soulisle.engine;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 词典层行为守卫（r41）。
 *
 * <p>与 {@code _test/engine_consistency_check.py} 的分工写死在这里，免得长成"同一判断两处实现"：
 * <ul>
 *   <li>那支判据负责 **JS 侧 == Java 侧** 的跨端对账（需要两端都在，跑在带外）；</li>
 *   <li>本类负责 **Java 侧自身的行为不变量**（危机短路、否定被程度覆盖、平分稳定序、四舍五入、
 *       次情绪 40% 门槛、空输入不炸）——这些在跨端对账里是**看不见的**：两端一起错就一起绿。</li>
 * </ul>
 * 所以这里不复刻准确率数字，也不新增第二份词表；断言只引用 SSOT 里已有的词。
 */
class EmotionEngineTest {

    private static String mainOf(String text) {
        return EmotionEngine.scan(text).emotion();
    }

    private static double scoreOf(String text, String emo) {
        return EmotionEngine.scan(text).all().stream()
                .filter(s -> s.emotion().equals(emo))
                .map(EmotionEngine.Score::score)
                .findFirst()
                .orElse(-1.0);
    }

    @Test
    @DisplayName("空输入与 null：判 calm、强度 0.25、无危机、all 为空（不得 NPE）")
    void emptyInput() {
        for (String t : new String[] {"", null, "   "}) {
            EmotionEngine.ScanResult r = EmotionEngine.scan(t);
            assertFalse(r.crisis());
            assertEquals("calm", r.emotion(), "输入=[" + t + "]");
            assertEquals(0.25, r.intensity(), 1e-9);
            assertTrue(r.all().isEmpty());
            assertEquals(3, r.color().length);
        }
    }

    @Test
    @DisplayName("基础命中：难过 -> sadness，开心 -> joy")
    void basicHit() {
        assertEquals("sadness", mainOf("心里有点难过"));
        assertEquals("joy", mainOf("今天很开心"));
    }

    @Test
    @DisplayName("危机短路：命中危机词即 crisis + 强度 1 + 危机色（与安全边界绑定，优先级最高）")
    void crisisShortCircuit() {
        for (String w : EmotionLexicon.CRISIS) {
            EmotionEngine.ScanResult r = EmotionEngine.scan("我" + w + "了");
            assertTrue(r.crisis(), "危机词未命中: " + w);
            assertEquals("crisis", r.emotion());
            assertEquals(1.0, r.intensity(), 1e-9);
            assertEquals(EmotionLexicon.CRISIS_COLOR[0], r.color()[0], 1e-9);
        }
    }

    @Test
    @DisplayName("否定生效：别难过 不判 sadness（否定窗内无程度词）")
    void negationApplies() {
        EmotionEngine.ScanResult r = EmotionEngine.scan("别难过");
        assertEquals("calm", r.emotion(), "被否定的情绪不得计入得分");
        assertTrue(r.all().isEmpty(), "all 应为空，实际=" + r.all());
    }

    @Test
    @DisplayName("否定被程度副词覆盖：特别难过 仍判 sadness（2026-09-23 修的缺陷，防回退）")
    void negationCoveredByDegree() {
        EmotionEngine.ScanResult r = EmotionEngine.scan("心里特别难过");
        assertEquals("sadness", r.emotion());
        // 1.0(权重) x 1.4(特别) = 1.4；同时"别"作为否定字被覆盖，不反号
        assertEquals(1.4, scoreOf("心里特别难过", "sadness"), 1e-9);
    }

    @Test
    @DisplayName("程度副词只放大不清零：很难过(1.4) > 难过(1.0)；有点难过(0.6) < 难过(1.0)")
    void degreeScaling() {
        double plain = scoreOf("难过", "sadness");
        assertEquals(1.0, plain, 1e-9);
        assertTrue(scoreOf("特别难过", "sadness") > plain);
        assertTrue(scoreOf("有点难过", "sadness") < plain);
        assertTrue(scoreOf("有点难过", "sadness") > 0, "轻微程度词不得把情绪清零");
    }

    @Test
    @DisplayName("多次命中累加：难过难过 = 2.0（同词重叠扫描按出现次数计）")
    void repeatedHitsAccumulate() {
        assertEquals(2.0, scoreOf("难过难过", "sadness"), 1e-9);
    }

    @Test
    @DisplayName("平分稳定序：既高兴又难过 -> 并列 1.0 时按 SSOT 插入序取 joy")
    void tieUsesStableInsertionOrder() {
        EmotionEngine.ScanResult r = EmotionEngine.scan("既高兴又难过");
        assertEquals(2, r.all().size(), "两类各 1.0，实际=" + r.all());
        assertEquals(r.all().get(0).score(), r.all().get(1).score(), 1e-9, "前提：两条同分");
        assertEquals("joy", r.emotion(), "稳定排序下须与 JS 同取插入序在前者");
    }

    @Test
    @DisplayName("得分保留两位小数（+v.toFixed(2) 同构），强度封顶 1")
    void scoreFormattingAndIntensityCap() {
        double s = scoreOf("有点难过", "sadness");
        assertEquals(Math.round(s * 100.0) / 100.0, s, 1e-9, "得分必须是两位小数");
        double many = scoreOf("难过难过难过难过难过", "sadness");
        assertEquals(5.0, many, 1e-9);
        assertTrue(EmotionEngine.scan("难过难过难过难过难过").intensity() <= 1.0);
    }

    @Test
    @DisplayName("all 按得分降序排列（前端星雾取前二着色依赖这个次序）")
    void allSortedDescending() {
        EmotionEngine.ScanResult r = EmotionEngine.scan("很开心，也有点难过，还有点焦虑");
        List<EmotionEngine.Score> all = r.all();
        assertTrue(all.size() >= 2, "样本应命中多类，实际=" + all);
        for (int i = 1; i < all.size(); i++) {
            assertTrue(all.get(i - 1).score() >= all.get(i).score(),
                    "次序错位: " + all);
        }
    }

    @Test
    @DisplayName("次情绪 40% 门槛：达标给第二名，不达标按单一情绪（不得把噪声渲成第二色）")
    void secondaryThreshold() {
        List<EmotionEngine.Score> ok = List.of(
                new EmotionEngine.Score("sadness", 1.0),
                new EmotionEngine.Score("fear", 0.5));
        assertEquals("fear", EmotionEngine.secondaryOf(ok, "sadness"));

        List<EmotionEngine.Score> weak = List.of(
                new EmotionEngine.Score("sadness", 1.0),
                new EmotionEngine.Score("fear", 0.3));
        assertNull(EmotionEngine.secondaryOf(weak, "sadness"));

        assertEquals(0.4, 1.0 * 0.4, 1e-9, "边界值本身须达标（>= 而非 >）");
        List<EmotionEngine.Score> edge = List.of(
                new EmotionEngine.Score("sadness", 1.0),
                new EmotionEngine.Score("fear", 0.4));
        assertEquals("fear", EmotionEngine.secondaryOf(edge, "sadness"));

        assertNull(EmotionEngine.secondaryOf(List.of(), "sadness"), "空列表不得抛");
        assertNull(EmotionEngine.secondaryOf(null, "sadness"), "null 不得抛");
        assertNull(EmotionEngine.secondaryOf(ok, "nope"), "主情绪不在列时按单一情绪处理");
    }
}
