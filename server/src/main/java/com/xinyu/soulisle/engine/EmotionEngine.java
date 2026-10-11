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
 * 其中 {@code before = text[max(0, idx-NEG_WINDOW), idx)}；命中否定词 {@code mult = -0.7}
 * （否定词被程度副词覆盖时不生效，见 {@link #hasNegation(String)}），
 * 再对 {@code before} 中命中的程度词逐个相乘；仅当总分 > 0 才计入。
 */
public final class EmotionEngine {

    private EmotionEngine() {}

    /**
     * 否定取词窗口（r112：3 → 4，与 JS {@code NEG_WINDOW} 同值，改一端必须改另一端）。
     *
     * <p>旧值 3 抓不到「没什么好难过的」这一族：否定词「没」距情绪词「难过」4 字，
     * 窗口只覆盖到「什么好」⇒ 否定不生效 ⇒ sadness 照常计分 ⇒ 判成低落。
     * 扩到 4 的代价是可能「跨过标点否定后面无关的情绪词」——首跑就踩中两条：
     * 「解释也【没】人信，愤怒」的「没」属于「没人信」、「什么都不【不】懂，好慌」的「不」属于「不懂」，
     * 两者都与后面的情绪词隔着一个逗号。故配 {@link #NEG_BREAK}：否定词与情绪词之间只要隔着
     * 标点/空白，修饰关系即不成立。另 2 条对抗样本钉住另一侧
     * （「我没什么事，就是特别难受」=低落 ／「没什么事，但我特别生气」=烦躁）。
     */
    public static final int NEG_WINDOW = 4;

    /** 否定词与情绪词之间的「断点」字符集（与 JS {@code NEG_BREAK} 同义）：出现即不构成修饰关系。 */
    private static final String NEG_BREAK = "，。！？、；：… \t\r\n,.!?;:";

    /** 单个情绪得分（score 已按 JS 的 {@code +v.toFixed(2)} 取两位） */
    public record Score(String emotion, double score) {}

    /** 扫描结果（与 JS 返回对象同构） */
    public record ScanResult(boolean crisis, String emotion, double intensity,
                             List<Score> all, double[] color) {}

    /**
     * 否定判定（2026-09-23 修缺陷，与 JS {@code hasNegation} 同构）：
     * 否定词的字符若**被程度副词覆盖**，则该否定词不生效。
     *
     * <p>背景：{@code NEG} 含「别」，取词窗口是「词前 {@value #NEG_WINDOW} 字」⇒「心里【特别】难受」里
     * 「特别」的「别」被当成否定词，sadness 乘 −0.7 反号后归零，最终误判成 anger。
     * 修正后：「特别难受」否定不生效（正确）；「别难过」否定照常生效（正确，保留）。
     */
    private static boolean hasNegation(String before) {
        List<int[]> degSpans = new ArrayList<>();
        for (String d : EmotionLexicon.DEG.keySet()) {
            int p = before.indexOf(d);
            while (p != -1) {
                degSpans.add(new int[] {p, p + d.length()});
                p = before.indexOf(d, p + 1);
            }
        }
        for (String n : EmotionLexicon.NEG) {
            int q = before.indexOf(n);
            while (q != -1) {
                boolean covered = false;
                for (int[] sp : degSpans) {
                    if (q < sp[1] && q + n.length() > sp[0]) {
                        covered = true;
                        break;
                    }
                }
                // 断点：否定词与情绪词之间隔着标点/空白 ⇒ 不是修饰关系，该否定词不生效
                boolean broken = before.substring(q + n.length())
                        .chars().anyMatch(c -> NEG_BREAK.indexOf(c) >= 0);
                if (!covered && !broken) {
                    return true;
                }
                q = before.indexOf(n, q + 1);
            }
        }
        return false;
    }

    /** 转折加权的两个倍率（与 JS {@code CONTRAST_BEFORE / CONTRAST_AFTER} 同值）：
     *  转折词**之前**的情绪降权、**之后**的升权。依据同 JS —— 要让转折后的弱情绪压过转折前的强情绪。 */
    public static final double CONTRAST_BEFORE = 0.6;
    public static final double CONTRAST_AFTER = 1.4;

    public static ScanResult scan(String text) {
        String t = text == null ? "" : text;
        Map<String, Double> scores = new LinkedHashMap<>();

        // 转折主次（r113，与 JS 同构）：以**首个**转折词为界，界取该词之后。
        // 之前的分句是让步（降权），之后才是说话人真正在表达的情绪（升权）。
        int pivot = -1;
        for (String c : EmotionLexicon.CONTRAST) {
            int p = t.indexOf(c);
            if (p != -1 && (pivot == -1 || p < pivot)) {
                pivot = p + c.length();
            }
        }

        for (Map.Entry<String, EmotionLexicon.Cfg> e : EmotionLexicon.LEX.entrySet()) {
            String emo = e.getKey();
            EmotionLexicon.Cfg cfg = e.getValue();
            double s = 0;
            for (String w : cfg.words()) {
                int idx = t.indexOf(w);
                while (idx != -1) {
                    String before = t.substring(Math.max(0, idx - NEG_WINDOW), idx);
                    double mult = 1;
                    if (hasNegation(before)) {
                        mult = -0.7;
                    }
                    for (Map.Entry<String, Double> d : EmotionLexicon.DEG.entrySet()) {
                        if (before.contains(d.getKey())) {
                            mult *= d.getValue();
                        }
                    }
                    if (pivot != -1) {
                        mult *= (idx < pivot ? CONTRAST_BEFORE : CONTRAST_AFTER);
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
