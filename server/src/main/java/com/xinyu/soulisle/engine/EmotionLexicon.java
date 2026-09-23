package com.xinyu.soulisle.engine;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 情绪词典与语义常量 —— 数据全部来自**唯一真相源** {@code src/data/emotion-lexicon.js}。
 *
 * <p>⚠️ 2026-09-23 起这里**不再硬编码任何词表**（J6 词表 SSOT 化）。
 * 此前 JS 侧 {@code src/js/emotion-engine.js} 与 Java 侧各维护一份，靠
 * {@code _test/engine_consistency_check.py} 事后比对（「受监控的重复」）。
 * 现在两端读**同一个文件**，结构上不可能再分叉；守卫脚本降级为回归验证
 * （验证两端加载器对同一份数据解析结果一致）。
 *
 * <p>路径解析（优先到后）：
 * <ol>
 *   <li>环境变量 {@code XINYU_LEXICON}（指向文件本身）</li>
 *   <li>环境变量 {@code XINYU_WEB_ROOT} + {@code /data/emotion-lexicon.js}
 *       —— Docker 里是 {@code /app/web}（镜像内前端目录），与静态页同源</li>
 *   <li>默认 {@code ./src/} + {@code /data/emotion-lexicon.js}
 *       —— 从项目根跑 fat jar 时命中前端权威源</li>
 * </ol>
 *
 * <p>⚠️ 加载失败一律 **fail-fast**（抛 IllegalStateException 终止启动），
 * 绝不能静默回退到旧词表 —— 回退会让「两端一致」变成假象。
 */
public final class EmotionLexicon {

    private EmotionLexicon() {}

    /** 单情绪配置：权重 / 渲染色 / 触发词 */
    public record Cfg(double weight, double[] color, List<String> words) {}

    /** 词表单一真相源的解析路径（只读，供健康检查与排障回显） */
    public static final String LEXICON_PATH = resolvePath();

    public static final Map<String, Cfg> LEX = new LinkedHashMap<>();

    /** 否定词（「不」的重复项在 SSOT 里原样保留，与 JS 一致） */
    public static final List<String> NEG;

    /** 程度修饰词：字面量 → 倍数（插入序与 SSOT 对象字面量一致） */
    public static final Map<String, Double> DEG = new LinkedHashMap<>();

    /** 危机词表：独立于情绪评分，命中即最高优先级（安全边界） */
    public static final List<String> CRISIS;

    /** 情绪枚举（顺序 = LEX 插入序，平分时的兜底顺序必须与 JS 一致） */
    public static final List<String> EMOTIONS;

    public static final double[] CRISIS_COLOR;

    private static final Map<String, String> LABELS = new LinkedHashMap<>();

    static {
        JsonNode root = readLexicon(LEXICON_PATH);

        JsonNode lexNode = root.get("lex");
        for (Iterator<String> it = lexNode.fieldNames(); it.hasNext(); ) {
            String emo = it.next();
            JsonNode n = lexNode.get(emo);
            LEX.put(emo, new Cfg(n.get("weight").asDouble(),
                    toDoubleArray(n.get("color")),
                    toStringList(n.get("words"))));
        }

        NEG = toStringList(root.get("neg"));

        JsonNode degNode = root.get("deg");
        for (Iterator<String> it = degNode.fieldNames(); it.hasNext(); ) {
            String k = it.next();
            DEG.put(k, degNode.get(k).asDouble());
        }

        CRISIS = toStringList(root.get("crisis"));
        CRISIS_COLOR = toDoubleArray(root.get("crisisColor"));

        JsonNode labelNode = root.get("labels");
        for (Iterator<String> it = labelNode.fieldNames(); it.hasNext(); ) {
            String k = it.next();
            LABELS.put(k, labelNode.get(k).asText());
        }

        EMOTIONS = List.copyOf(LEX.keySet());
    }

    private static String resolvePath() {
        String p = System.getenv("XINYU_LEXICON");
        if (p != null && !p.isBlank()) {
            return p;
        }
        String root = System.getenv("XINYU_WEB_ROOT");
        if (root == null || root.isBlank()) {
            root = "./src/";
        }
        return root.replaceAll("/+$", "") + "/data/emotion-lexicon.js";
    }

    /**
     * 读取 SSOT：文件体是 {@code window.__XINYU_LEXICON__ = { ... };}
     * （做成 .js 是让零构建的前端能同步加载），这里只取首尾花括号之间的纯 JSON。
     */
    private static JsonNode readLexicon(String path) {
        Path p = Path.of(path);
        try {
            String raw = Files.readString(p, StandardCharsets.UTF_8);
            /* 必须先剥掉注释再定位（两次实测踩坑，勿简化）：
             *   ① 注释里出现过 ${XINYU_LEXICON} 这种带花括号的文字 → 全文第一个 { 落在注释里；
             *   ② 注释里还写过 `（经 window.__XINYU_LEXICON__）` → 标记定位同样会被带偏。
             * 剥注释后剩下的就只有 `window.__XINYU_LEXICON__ = { ... };` 这一条语句。 */
            String code = raw.replaceAll("(?s)/\\*.*?\\*/", "").replaceAll("(?m)^\\s*//.*$", "");
            int marker = code.indexOf("__XINYU_LEXICON__");
            int s = code.indexOf('{', Math.max(0, marker));
            int e = code.lastIndexOf('}');
            if (marker < 0 || s < 0 || e <= s) {
                throw new IllegalStateException(
                        "文件里找不到 `window.__XINYU_LEXICON__ = { ... }` 形式的 JSON 字面量");
            }
            return new ObjectMapper().readTree(code.substring(s, e + 1));
        } catch (Exception ex) {
            throw new IllegalStateException(
                    "加载情绪词表失败（单一真相源，不能静默回退）: " + p.toAbsolutePath().normalize(), ex);
        }
    }

    private static List<String> toStringList(JsonNode n) {
        List<String> out = new ArrayList<>();
        if (n != null) {
            for (JsonNode x : n) {
                out.add(x.asText());
            }
        }
        return List.copyOf(out);
    }

    private static double[] toDoubleArray(JsonNode n) {
        double[] out = new double[n.size()];
        for (int i = 0; i < n.size(); i++) {
            out[i] = n.get(i).asDouble();
        }
        return out;
    }

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
