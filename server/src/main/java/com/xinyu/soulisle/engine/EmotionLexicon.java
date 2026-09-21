package com.xinyu.soulisle.engine;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 情绪词典与语义常量 —— **逐字对齐** {@code src/js/emotion-engine.js}。
 *
 * <p>⚠️ 移植保真要点：JS 词表里 {@code sadness} 的「难受」与 {@code NEG} 的「不」**各有一处重复**，
 * 而 JS 是逐项累加 → 重复项会被**重复计分**。此处必须原样保留，否则准确率对不上 94.4%。
 *
 * <p>修改词表前先改 JS 权威源并重跑 {@code node _test/emotion_eval.js}，禁止只改一侧。
 */
public final class EmotionLexicon {

    private EmotionLexicon() {}

    /** 单情绪配置：权重 / 渲染色 / 触发词 */
    public record Cfg(double weight, double[] color, List<String> words) {}

    public static final Map<String, Cfg> LEX = new LinkedHashMap<>();

    static {
        LEX.put("joy", new Cfg(1.0, new double[]{1.00, 0.82, 0.30}, List.of(
                "开心", "高兴", "快乐", "爽", "棒", "太好了", "爱", "幸福", "满足", "期待",
                "哈哈", "嘿嘿", "顺利", "成功", "上岸", "录取", "offer", "涨薪", "被夸", "惊喜",
                "小确幸", "通过了", "评上了", "考上了")));
        LEX.put("sadness", new Cfg(1.0, new double[]{0.30, 0.49, 1.00}, List.of(
                "难过", "伤心", "哭", "想哭", "失落", "孤独", "孤单", "emo", "抑郁", "低落",
                "难受", "心碎", "失望", "遗憾", "空落落", "没意思", "好累", "疲惫", "累", "难受",
                "心情不好", "不开心", "白费")));
        LEX.put("anger", new Cfg(1.0, new double[]{1.00, 0.23, 0.19}, List.of(
                "生气", "气死", "烦", "烦躁", "火大", "愤怒", "讨厌", "恶心", "受不了", "凭什么",
                "骂", "吵架", "不公平", "破防")));
        LEX.put("fear", new Cfg(1.0, new double[]{0.62, 0.40, 0.95}, List.of(
                "害怕", "恐惧", "慌", "紧张", "担心", "焦虑", "不安", "怕", "吓人", "噩梦",
                "失眠", "睡不着", "压力", "压力好大", "崩溃", "要死了", "赶不上", "挂科", "施压", "答辩",
                "交代")));
        LEX.put("calm", new Cfg(0.8, new double[]{0.25, 0.85, 0.75}, List.of(
                "平静", "还行", "一般", "普通", "安静", "放松", "舒服", "还好", "凑合", "正常", "平淡")));
        LEX.put("love", new Cfg(0.9, new double[]{0.98, 0.42, 0.78}, List.of(
                "心动", "暗恋", "想他", "想她", "想TA", "表白", "在一起", "分手", "失恋", "想念",
                "舍不得", "暧昧", "喜欢上")));
    }

    /** 否定词（「不」重复项保留，与 JS 一致） */
    public static final List<String> NEG = List.of("不", "没", "没有", "别", "无", "并非", "不太", "不算", "不");

    /** 程度修饰词：字面量 → 倍数（插入序与 JS 对象字面量一致） */
    public static final Map<String, Double> DEG = new LinkedHashMap<>();

    static {
        DEG.put("太", 1.4);
        DEG.put("好", 1.3);
        DEG.put("非常", 1.5);
        DEG.put("特别", 1.4);
        DEG.put("超", 1.5);
        DEG.put("真的", 1.3);
        DEG.put("巨", 1.5);
        DEG.put("有点", 0.6);
        DEG.put("有些", 0.6);
        DEG.put("稍微", 0.5);
    }

    /** 危机词表：独立于情绪评分，命中即最高优先级（安全边界） */
    public static final List<String> CRISIS = List.of(
            "自杀", "不想活", "活不下去", "结束生命", "割腕", "轻生", "一了百了",
            "死了算了", "去死", "自我了断", "结束一切", "想结束");

    /** 情绪枚举（顺序 = LEX 插入序，平分时的兜底顺序必须与 JS 一致） */
    public static final List<String> EMOTIONS = List.of("joy", "sadness", "anger", "fear", "calm", "love");

    public static final double[] CRISIS_COLOR = {1.0, 0.2, 0.25};

    private static final Map<String, String> LABELS = Map.of(
            "joy", "愉悦", "sadness", "低落", "anger", "烦躁",
            "fear", "焦虑", "calm", "平静", "love", "心动", "crisis", "危机信号");

    public static double[] colorOf(String emotion) {
        if ("crisis".equals(emotion)) {
            return CRISIS_COLOR.clone();
        }
        Cfg cfg = LEX.get(emotion);
        return (cfg == null ? LEX.get("calm") : cfg).color().clone();
    }

    public static String labelOf(String emotion) {
        return LABELS.getOrDefault(emotion, "平静");
    }
}
