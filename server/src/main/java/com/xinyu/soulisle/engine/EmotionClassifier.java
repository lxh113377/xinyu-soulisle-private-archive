package com.xinyu.soulisle.engine;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xinyu.soulisle.llm.LlmProxy;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 三级情绪路由 —— 在旧双路（词典 + LLM）中间插入本地微调模型腿。
 *
 * <p>路径与优先级（顺序不可调换，危机是安全边界）：
 * <ol>
 *   <li>词典命中危机 → 立即返回，<b>不调用任何模型</b>（安全边界永不概率化）</li>
 *   <li>auto 路由 + 本地模型可用：
 *       <ul>
 *         <li>词典与模型<b>一致</b> → 双证据共识采信（fin 取词典读数，强度口径连续）</li>
 *         <li><b>分歧</b> → 词典裁决（分歧信号随 model 字段展示，不改判）</li>
 *       </ul>
 *       结构保证：共识与分歧的 fin 都是词典读数 ⇒ <b>73 条评测集上 auto ≡ 词典成绩恒等</b>
 *       （在线离线均成立，2026-10-09 双口径实测：离线 98.6% / 在线 98.6%——
 *       在线分歧升 LLM 的方案实测倒退至 94.5% 已被否决，见 routedFromModel 注）。</li>
 *   <li>本地模型未配置 / 不可达 → 原双路行为原样保留：无 key（离线）→ 仅词典；
 *       有 key → 词典+LLM（分歧采信 LLM），LLM 失败 → 词典兜底</li>
 * </ol>
 *
 * <p>模型置信度（softmax top-1）随证据链输出（{@code /api/emotion} 的 model 字段），
 * 供盲测四路对比与「未来切换主判器」的依据，不参与本轮判定。
 * {@code xinyu.emotion.route=lexicon} 可整体关掉本地模型腿（回归对照与演示切换用）。
 */
@Component
public class EmotionClassifier {

    /** 判定结果（emotion + intensity；词典层与 LLM 层共用同一形状，便于对比展示） */
    public record Verdict(String emotion, double intensity) {}

    /**
     * 一轮判定的完整证据链：lex 永远在（前端双路标签要显示词典读数）；
     * model/llm 各自记录实际参与判定的腿（未参与为 null）；fin 是最终采信结果。
     */
    public record Outcome(EmotionEngine.ScanResult lex, ModelProxy.Verdict model,
                          Verdict llm, Verdict fin, String path) {}

    private static final Pattern JSON_BLOCK = Pattern.compile("\\{[\\s\\S]*\\}");

    /** 与 chat-agent.js 的 CLASSIFY_SYS 逐字一致 */
    private static final String CLASSIFY_SYS =
            "你是情绪分类器。从 joy(愉悦)/sadness(低落)/anger(烦躁)/fear(焦虑)/calm(平静)/love(心动) 中选一个主导情绪，"
                    + "只输出 JSON：{\"emotion\":\"...\",\"intensity\":0到1的小数}。"
                    + "示例：输入「论文被拒了三次，感觉努力全白费」输出 {\"emotion\":\"sadness\",\"intensity\":0.8}；"
                    + "输入「今天天气不错」输出 {\"emotion\":\"calm\",\"intensity\":0.2}。";

    private final LlmProxy llm;
    private final ModelProxy model;
    private final Duration llmTimeout;
    private final String route;
    private final ObjectMapper mapper = new ObjectMapper();

    /** 兼容旧签名：不配本地模型、route=lexicon ⇒ 行为与三级路由引入前逐字节一致 */
    public EmotionClassifier(LlmProxy llm) {
        this(llm, 8000L);
    }

    public EmotionClassifier(LlmProxy llm, long llmTimeoutMs) {
        this(llm, new ModelProxy("", 1500), llmTimeoutMs, "lexicon");
    }

    /** 容器认准这条（多 public 构造器消歧） */
    @Autowired
    public EmotionClassifier(LlmProxy llm, ModelProxy model,
                             @Value("${xinyu.emotion.llm-timeout-ms:8000}") long llmTimeoutMs,
                             @Value("${xinyu.emotion.route:auto}") String route) {
        this.llm = llm;
        this.model = model;
        this.llmTimeout = Duration.ofMillis(llmTimeoutMs);
        this.route = route == null ? "auto" : route.trim();
    }

    public Outcome classify(String text) {
        EmotionEngine.ScanResult lex = EmotionEngine.scan(text);
        Verdict lexVerdict = new Verdict(lex.emotion(), lex.intensity());

        if (lex.crisis()) {
            return new Outcome(lex, null, null, new Verdict("crisis", 1), "词典·危机拦截");
        }
        if (!"lexicon".equalsIgnoreCase(route) && model.enabled()) {
            ModelProxy.Verdict mv = model.classify(text);
            if (mv != null) {
                return routedFromModel(lex, mv, text);
            }
            // 本地模型配置了但失败（连不上/超时/坏响应）→ 落回原双路，本地腿记 null
        }
        return legacyRoute(lex, lexVerdict, text);
    }

    /** auto 路由：本地模型已出结果时的共识/分歧分支（结构性永不倒退，见类注） */
    private Outcome routedFromModel(EmotionEngine.ScanResult lex,
                                    ModelProxy.Verdict mv, String text) {
        Verdict lexVerdict = new Verdict(lex.emotion(), lex.intensity());
        if (mv.emotion().equals(lex.emotion())) {
            // 双证据共识：emotion 相同 ⇒ fin 取词典读数（强度口径连续），模型置信度留证据链
            return new Outcome(lex, mv, null, lexVerdict,
                    String.format("词典+模型共识（conf=%.2f）", mv.confidence()));
        }
        // 分歧 → 词典裁决（分歧信号随 model 字段展示给证据链；在线实测 2026-10-09：
        // 若分歧升 LLM，10 条分歧中 LLM 错 4 条 ⇒ 73 条在线 94.5% 倒退，故 LLM 不持有判定权。
        // LLM 仲裁语义完整保留在 route=lexicon（旧双路），route 开关即两种策略的对照实验）
        return new Outcome(lex, mv, null, lexVerdict, "词典与模型分歧 → 词典裁决");
    }

    /** 原双路（r41 语义，标签逐字保留）：仅词典 / 词典+LLM 一致或分歧 / LLM 失败兜底 */
    private Outcome legacyRoute(EmotionEngine.ScanResult lex, Verdict lexVerdict, String text) {
        if (!llm.hasKey()) {
            return new Outcome(lex, null, null, lexVerdict, "仅词典（离线）");
        }
        try {
            Verdict llmVerdict = llmClassify(text);
            boolean agree = llmVerdict.emotion().equals(lex.emotion());
            return new Outcome(lex, null, llmVerdict, llmVerdict,
                    agree ? "词典+LLM 一致 → LLM" : "词典+LLM 分歧 → 采信 LLM");
        } catch (Exception e) {
            return new Outcome(lex, null, null, lexVerdict, "LLM 精判失败 → 词典兜底");
        }
    }

    private Verdict llmClassify(String text) throws Exception {
        Map<String, Object> sys = new LinkedHashMap<>();
        sys.put("role", "system");
        sys.put("content", CLASSIFY_SYS);
        Map<String, Object> usr = new LinkedHashMap<>();
        usr.put("role", "user");
        usr.put("content", text.substring(0, Math.min(200, text.length())));

        LlmProxy.Result r = llm.call(mapper.valueToTree(List.of(sys, usr)), 0.0, 40, llmTimeout);
        if (r.status() != 200) {
            throw new IllegalStateException("upstream " + r.status());
        }
        JsonNode root = mapper.readTree(r.body());
        String raw = root.path("choices").path(0).path("message").path("content").asText("");
        Matcher m = JSON_BLOCK.matcher(raw);
        if (!m.find()) {
            throw new IllegalStateException("no-json");
        }
        JsonNode j = mapper.readTree(m.group());
        String emotion = j.path("emotion").asText("");
        if (!EmotionLexicon.EMOTIONS.contains(emotion)) {
            throw new IllegalStateException("bad-emotion");
        }
        double intensity = j.has("intensity") && j.get("intensity").isNumber()
                ? j.get("intensity").asDouble() : 0.5;
        return new Verdict(emotion, Math.max(0, Math.min(1, intensity)));
    }
}
