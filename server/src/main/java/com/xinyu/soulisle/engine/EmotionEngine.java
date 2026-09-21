package com.xinyu.soulisle.engine;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 本地情感引擎（词典层）—— 1:1 对齐 {@code src/js/emotion-engine.js} 的 {@code scan()}。
 *
 * <p>评分公式与 JS 完全一致：对每个情绪累加 {@code weight × mult}，
 * 其中 {@code before = text[max(0, idx-3), idx)}；命中否定词 {@code mult = -0.7}，
 * 再对 {@code before} 中命中的程度词逐个相乘；仅当总分 > 0 才计入。
 */
public final class EmotionEngine {

    private EmotionEngine() {}

    /** 单个情绪得分（score 已按 JS 的 {@code +v.toFixed(2)} 取两位） */
    public record Score(String emotion, double score) {}

    /** 扫描结果（与 JS 返回对象同构） */
    public record ScanResult(boolean crisis, String emotion, double intensity,
                             List<Score> all, double[] color) {}

    public static ScanResult scan(String text) {
        String t = text == null ? "" : text;
        Map<String, Double> scores = new LinkedHashMap<>();

        for (Map.Entry<String, EmotionLexicon.Cfg> e : EmotionLexicon.LEX.entrySet()) {
            String emo = e.getKey();
            EmotionLexicon.Cfg cfg = e.getValue();
            double s = 0;
            for (String w : cfg.words()) {
                int idx = t.indexOf(w);
                while (idx != -1) {
                    String before = t.substring(Math.max(0, idx - 3), idx);
                    double mult = 1;
                    for (String n : EmotionLexicon.NEG) {
                        if (before.contains(n)) {
                            mult = -0.7;
                            break;
                        }
                    }
                    for (Map.Entry<String, Double> d : EmotionLexicon.DEG.entrySet()) {
                        if (before.contains(d.getKey())) {
                            mult *= d.getValue();
                        }
                    }
                    s += cfg.weight() * mult;
                    idx = t.indexOf(w, idx + w.length());
                }
            }
            if (s > 0) {
                scores.put(emo, s);
            }
        }

        boolean crisis = EmotionLexicon.CRISIS.stream().anyMatch(t::contains);
        String emotion = "calm";
        double intensity = 0.25;

        // 稳定排序：JS 的 Array.sort 在现代引擎里稳定，平分时保留 LEX 插入序
        List<Map.Entry<String, Double>> entries = new ArrayList<>(scores.entrySet());
        entries.sort(Comparator.comparingDouble((Map.Entry<String, Double> x) -> x.getValue()).reversed());
        if (!entries.isEmpty()) {
            emotion = entries.get(0).getKey();
            intensity = Math.min(1, 0.3 + entries.get(0).getValue() * 0.25);
        }

        List<Score> all = new ArrayList<>();
        for (Map.Entry<String, Double> x : entries) {
            all.add(new Score(x.getKey(), Math.round(x.getValue() * 100.0) / 100.0));
        }

        String mainEmotion = emotion;
        return new ScanResult(
                crisis,
                crisis ? "crisis" : mainEmotion,
                crisis ? 1 : intensity,
                all,
                crisis ? EmotionLexicon.CRISIS_COLOR.clone() : EmotionLexicon.colorOf(mainEmotion));
    }

    /**
     * 次情绪判定：除主情绪外的第一名，且强度须达主情绪的 40%，否则按单一情绪处理
     * （与 JS {@code secondaryOf} 同规则，避免把噪声词渲染成第二种星雾颜色）。
     */
    public static String secondaryOf(List<Score> all, String main) {
        if (all == null || all.isEmpty()) {
            return null;
        }
        Score mainItem = null;
        List<Score> rest = new ArrayList<>();
        for (Score s : all) {
            if (s.emotion().equals(main)) {
                mainItem = s;
            } else {
                rest.add(s);
            }
        }
        if (mainItem == null || rest.isEmpty()) {
            return null;
        }
        Score top = rest.get(0);
        return top.score() >= mainItem.score() * 0.4 ? top.emotion() : null;
    }
}
