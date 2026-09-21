package com.xinyu.soulisle.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xinyu.soulisle.engine.EmotionClassifier;
import com.xinyu.soulisle.engine.EmotionEngine;
import com.xinyu.soulisle.engine.EmotionLexicon;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 情绪引擎 API。
 * <ul>
 *   <li>{@code POST /api/emotion} —— 双路识别，返回两路结果与采信路径（供证据展示）</li>
 *   <li>{@code GET  /api/emotion/eval} —— 在 Java 侧复跑 36 条评测集，输出与
 *       {@code _test/emotion_eval.js} 同构，便于两端直接对账</li>
 * </ul>
 */
@RestController
public class EmotionController {

    private final ObjectMapper mapper = new ObjectMapper();
    private final EmotionClassifier classifier;
    private final String datasetPath;

    public EmotionController(EmotionClassifier classifier,
                             @Value("${xinyu.eval.dataset}") String datasetPath) {
        this.classifier = classifier;
        this.datasetPath = datasetPath;
    }

    @PostMapping("/api/emotion")
    public ResponseEntity<byte[]> emotion(@RequestBody(required = false) String raw) {
        JsonNode node;
        try {
            node = mapper.readTree(raw == null ? "" : raw);
        } catch (Exception e) {
            return json(400, "{\"error\":\"bad-json\"}");
        }
        if (node == null || !node.isObject() || !node.hasNonNull("text")) {
            return json(400, "{\"error\":\"bad-json\"}");
        }
        String text = node.get("text").asText();

        EmotionClassifier.Outcome o = classifier.classify(text);
        EmotionEngine.ScanResult lex = o.lex();
        String mainEmotion = o.fin().emotion();
        String secondary = EmotionEngine.secondaryOf(lex.all(), mainEmotion);

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("lex", lexJson(lex));
        body.put("llm", o.llm() == null ? null : verdictJson(o.llm()));
        body.put("final", verdictJson(o.fin()));
        body.put("path", o.path());
        body.put("secondary", secondary);
        body.put("label", EmotionLexicon.labelOf(mainEmotion));
        body.put("color", EmotionLexicon.colorOf(mainEmotion));
        return json(200, write(body));
    }

    /**
     * 导出 Java 侧词表（供与 JS 侧做**一致性守卫**）。
     *
     * <p>为什么需要它：情绪引擎在 JS / Java 各有一份实现（离线降级需要本地那份），
     * 只比对「评测汇总指标」可能因巧合相同而漏掉个别条目分叉 ——
     * 直接比对**词表结构本身**才能抓到「改一边忘一边」。
     */
    @GetMapping("/api/emotion/lexicon")
    public ResponseEntity<byte[]> lexicon() {
        Map<String, Object> lex = new LinkedHashMap<>();
        for (Map.Entry<String, EmotionLexicon.Cfg> e : EmotionLexicon.LEX.entrySet()) {
            Map<String, Object> c = new LinkedHashMap<>();
            c.put("weight", e.getValue().weight());
            c.put("color", e.getValue().color());
            c.put("words", e.getValue().words());
            lex.put(e.getKey(), c);
        }
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("lex", lex);
        body.put("neg", EmotionLexicon.NEG);
        body.put("deg", EmotionLexicon.DEG);
        body.put("crisis", EmotionLexicon.CRISIS);
        return json(200, write(body));
    }

    /**
     * 复跑评测集：词典层准确率 + 危机召回（通过线 94.4% / 3-3）。
     *
     * @param detail 1 = 额外返回逐条 {@code {text,expect,pred}}（供一致性守卫**逐条**比对，
     *               避免只看汇总指标漏掉个别分叉）
     */
    @GetMapping("/api/emotion/eval")
    public ResponseEntity<byte[]> eval(@RequestParam(defaultValue = "0") int detail) {
        Path ds = Path.of(datasetPath).toAbsolutePath().normalize();
        if (!Files.isRegularFile(ds)) {
            return json(404, "{\"error\":\"dataset-not-found\",\"path\":\"" + escape(ds.toString()) + "\"}");
        }
        JsonNode root;
        try {
            root = mapper.readTree(Files.readString(ds, StandardCharsets.UTF_8));
        } catch (Exception e) {
            return json(500, "{\"error\":\"dataset-unreadable\"}");
        }
        JsonNode items = root.path("items");
        if (!items.isArray() || items.isEmpty()) {
            return json(500, "{\"error\":\"dataset-empty\"}");
        }

        int correct = 0;
        Map<String, int[]> perClass = new LinkedHashMap<>();
        List<Map<String, Object>> misses = new ArrayList<>();
        List<Map<String, Object>> results = new ArrayList<>();
        List<JsonNode> crisisItems = new ArrayList<>();
        int crisisHit = 0;

        for (JsonNode it : items) {
            String text = it.path("text").asText();
            String expect = it.path("expect").asText();
            EmotionEngine.ScanResult r = EmotionEngine.scan(text);

            if (detail == 1) {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("text", text);
                row.put("expect", expect);
                row.put("pred", r.emotion());
                results.add(row);
            }

            int[] slot = perClass.computeIfAbsent(expect, k -> new int[2]);
            slot[1]++;
            if (r.emotion().equals(expect)) {
                correct++;
                slot[0]++;
            } else {
                Map<String, Object> miss = new LinkedHashMap<>();
                miss.put("text", text);
                miss.put("expect", expect);
                miss.put("pred", r.emotion());
                misses.add(miss);
            }
            if ("crisis".equals(expect)) {
                crisisItems.add(it);
                if (r.crisis()) {
                    crisisHit++;
                }
            }
        }

        int total = items.size();
        Map<String, Object> perClassOut = new LinkedHashMap<>();
        perClass.forEach((k, v) -> perClassOut.put(k, v[0] + "/" + v[1]));

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("total", total);
        body.put("accuracy", Math.round(correct * 1000.0 / total) / 10.0 + "%");
        body.put("crisis_recall", crisisHit + "/" + crisisItems.size());
        body.put("per_class", perClassOut);
        body.put("misses", misses);
        if (detail == 1) {
            body.put("results", results);
        }
        return json(200, write(body));
    }

    private Map<String, Object> lexJson(EmotionEngine.ScanResult lex) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("crisis", lex.crisis());
        m.put("emotion", lex.emotion());
        m.put("intensity", lex.intensity());
        List<Map<String, Object>> all = new ArrayList<>();
        for (EmotionEngine.Score s : lex.all()) {
            Map<String, Object> x = new LinkedHashMap<>();
            x.put("emotion", s.emotion());
            x.put("score", s.score());
            all.add(x);
        }
        m.put("all", all);
        m.put("color", lex.color());
        return m;
    }

    private Map<String, Object> verdictJson(EmotionClassifier.Verdict v) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("emotion", v.emotion());
        m.put("intensity", v.intensity());
        return m;
    }

    private String write(Object o) {
        try {
            return mapper.writeValueAsString(o);
        } catch (Exception e) {
            return "{\"error\":\"serialize\"}";
        }
    }

    private String escape(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    private ResponseEntity<byte[]> json(int status, String body) {
        return ResponseEntity.status(status)
                .contentType(MediaType.APPLICATION_JSON)
                .body(body.getBytes(StandardCharsets.UTF_8));
    }
}
