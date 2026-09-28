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
 * 双路情绪识别 —— 1:1 对齐 {@code src/js/chat-agent.js} 的 {@code classifyEmotion()}。
 *
 * <p>路径与优先级（顺序不可调换，危机是安全边界）：
 * <ol>
 *   <li>词典命中危机 → 立即返回，<b>不调用 LLM</b></li>
 *   <li>无 key（离线）→ 仅词典</li>
 *   <li>词典 + LLM 一致 → 采信 LLM</li>
 *   <li>词典 + LLM 分歧 → <b>采信 LLM</b></li>
 *   <li>LLM 失败 → 词典兜底</li>
 * </ol>
 */
@Component
public class EmotionClassifier {

    /** 判定结果（emotion + intensity；词典层与 LLM 层共用同一形状，便于对比展示） */
    public record Verdict(String emotion, double intensity) {}

    public record Outcome(EmotionEngine.ScanResult lex, Verdict llm, Verdict fin, String path) {}

    private static final Pattern JSON_BLOCK = Pattern.compile("\\{[\\s\\S]*\\}");

    /** 与 chat-agent.js 的 CLASSIFY_SYS 逐字一致 */
    private static final String CLASSIFY_SYS =
            "你是情绪分类器。从 joy(愉悦)/sadness(低落)/anger(烦躁)/fear(焦虑)/calm(平静)/love(心动) 中选一个主导情绪，"
                    + "只输出 JSON：{\"emotion\":\"...\",\"intensity\":0到1的小数}。"
                    + "示例：输入「论文被拒了三次，感觉努力全白费」输出 {\"emotion\":\"sadness\",\"intensity\":0.8}；"
                    + "输入「今天天气不错」输出 {\"emotion\":\"calm\",\"intensity\":0.2}。";

    private final LlmProxy llm;
    private final Duration llmTimeout;
    private final ObjectMapper mapper = new ObjectMapper();

    public EmotionClassifier(LlmProxy llm) {
        this(llm, 8000L);
    }

    /**
     * r70：双路里「LLM 精判」这一腿的请求级超时可配。此前它复用聊天链路的 60s ——
     * 上游挂起时一条 {@code POST /api/emotion} 会占住一个工作线程整整一分钟才回落词典，
     * 而同一条链的前端侧在 r51/r65 已被压到 15s 与整轮看门狗。危机词仍不调上游（优先级不变）。
     *
     * <p>标 @Autowired 是让容器在两个 public 构造器里认准这条（否则启动即消歧失败）。
     */
    @Autowired
    public EmotionClassifier(LlmProxy llm,
                             @Value("${xinyu.emotion.llm-timeout-ms:8000}") long llmTimeoutMs) {
        this.llm = llm;
        this.llmTimeout = Duration.ofMillis(llmTimeoutMs);
    }

    public Outcome classify(String text) {
        EmotionEngine.ScanResult lex = EmotionEngine.scan(text);
        Verdict lexVerdict = new Verdict(lex.emotion(), lex.intensity());

        if (lex.crisis()) {
            return new Outcome(lex, null, new Verdict("crisis", 1), "词典·危机拦截");
        }
        if (!llm.hasKey()) {
            return new Outcome(lex, null, lexVerdict, "仅词典（离线）");
        }
        try {
            Verdict llmVerdict = llmClassify(text);
            boolean agree = llmVerdict.emotion().equals(lex.emotion());
            return new Outcome(lex, llmVerdict, llmVerdict,
                    agree ? "词典+LLM 一致 → LLM" : "词典+LLM 分歧 → 采信 LLM");
        } catch (Exception e) {
            return new Outcome(lex, null, lexVerdict, "LLM 精判失败 → 词典兜底");
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
