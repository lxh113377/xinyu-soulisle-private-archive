package com.xinyu.soulisle.service;

import com.xinyu.soulisle.entity.ChatMessage;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 长期记忆检索（r128 新增）：BM25 打分器，零新依赖的纯函数。
 *
 * <p><b>为什么不是向量检索</b>：本仓架构决策 #1 写死了「需要 Embedding / 向量检索时，
 * 形态应是 Java 管业务 API + Python 管模型服务」。向量库那一格对标面上是 9/16（r127 现读），
 * 确实是最大差距，但上向量就等于当场推翻决策 #1 —— 那是要老大拍板的事，不是一个自动化轮该
 * 单方面干的事。
 *
 * <p>于是走**轻量解**：BM25 是 1994 年的词频统计算法，纯 Java、零依赖、零模型下载，
 * 在「几百条到几千条历史消息」这个量级上召回质量完全够用。它买到的是**检索能力本身**
 * （能问「我上次说过什么」而不是只能倒序翻页），而不是向量那套语义泛化。
 *
 * <p><b>中文怎么切</b>：不引分词库，用 **CJK 二元组（bigram）**。「今天心情不好」切成
 * 今天/天天/天心/心情/情不/不好，「考试焦虑」切成 考试/试焦/焦虑 —— 共享字bigram 天然
 * 构成召回桥梁，且零词典零依赖。ASCII 走小写单词切分。
 *
 * <p><b>纯函数</b>：只吃 {@code List<ChatMessage>} 吐 {@code List<Hit>}，不碰数据库、不碰
 * Spring 容器，因此可以在纯 JUnit 里被穷举测完。
 */
public final class MemorySearchService {

    /** BM25 的两个调参：k1 管词频饱和，b 管长文档惩罚 */
    private static final double K1 = 1.2;
    private static final double B = 0.75;

    private MemorySearchService() {
    }

    /** 一条命中：原消息 + 分值（分值只在本次候选集内可比，不是跨查询的绝对相关度） */
    public record Hit(ChatMessage message, double score) {}

    /**
     * 对候选集按 BM25 排序。
     *
     * @param documents 候选文档（通常是某会话最近若干条消息）
     * @param query     查询串；空白或无有效词元时返回空列表
     * @param limit     返回条数上限；<=0 视为 10
     */
    public static List<Hit> search(List<ChatMessage> documents, String query, int limit) {
        // 先归一 limit：Javadoc 承诺「<=0 视为 10」，不归一的话 subList(0, -5) 会当场抛栈
        int take = limit <= 0 ? 10 : limit;
        List<String> queryTerms = tokenize(query);
        if (documents == null || documents.isEmpty() || queryTerms.isEmpty()) {
            return List.of();
        }

        int n = documents.size();
        // 预切词：文档集小，一次切完比每篇重复切便宜
        List<List<String>> docTerms = new ArrayList<>(n);
        double totalLength = 0;
        for (ChatMessage m : documents) {
            List<String> terms = tokenize(m == null ? null : m.getContent());
            docTerms.add(terms);
            totalLength += terms.size();
        }
        double avgLength = totalLength / n;

        Map<String, Integer> docFreq = new HashMap<>();
        for (List<String> terms : docTerms) {
            for (String t : new LinkedHashSet<>(terms)) {
                docFreq.merge(t, 1, Integer::sum);
            }
        }

        Map<String, Double> idf = new LinkedHashMap<>();
        for (String t : queryTerms) {
            int df = docFreq.getOrDefault(t, 0);
            if (df == 0) {
                continue;   // 该词在候选集里一次都没出现，留着只会给 0 分噪声
            }
            // 加 1 的 IDF：保证非负，避免高频词给出负分把排序搞反
            idf.put(t, Math.log(1.0 + (n - df + 0.5) / (df + 0.5)));
        }
        if (idf.isEmpty()) {
            return List.of();
        }

        List<Hit> hits = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            double score = 0;
            Map<String, Integer> tf = termFreq(docTerms.get(i));
            for (Map.Entry<String, Double> e : idf.entrySet()) {
                Integer f = tf.get(e.getKey());
                if (f == null) {
                    continue;
                }
                double freq = f;
                double norm = freq * (K1 + 1)
                        / (freq + K1 * (1 - B + B * docTerms.get(i).size() / avgLength));
                score += e.getValue() * norm;
            }
            if (score > 0) {
                hits.add(new Hit(documents.get(i), score));
            }
        }

        // 同分时按 id 倒序（新的在前），保证排序稳定可复现 —— 判据要能断言顺序
        hits.sort(Comparator.comparingDouble(Hit::score).reversed()
                .thenComparing(h -> h.message() == null || h.message().getId() == null
                        ? Long.MIN_VALUE : h.message().getId(), Comparator.reverseOrder()));
        return hits.size() > take ? new ArrayList<>(hits.subList(0, take)) : hits;
    }

    /**
     * 词元切分：CJK 走二元组，非 CJK 走小写单词。
     *
     * <p>单字不单独成词元 —— 一个字的信息量太低，「我」「的」「了」这类高频字会让召回
     * 全被虚高。只有 bigram 的话单字查询（例如只输入一个字）就召回不到，这是刻意的
     * 取舍：宁可让单字查询返回空，也不要给一屏噪声。
     */
    static List<String> tokenize(String text) {
        if (text == null || text.isBlank()) {
            return List.of();
        }
        List<String> out = new ArrayList<>();
        StringBuilder cjkRun = new StringBuilder();
        StringBuilder word = new StringBuilder();

        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (isCjk(c)) {
                if (word.length() > 0) {
                    out.add(word.toString().toLowerCase());
                    word.setLength(0);
                }
                cjkRun.append(c);
            } else if (Character.isLetterOrDigit(c)) {
                if (cjkRun.length() > 0) {
                    addBigrams(cjkRun, out);
                    cjkRun.setLength(0);
                }
                word.append(c);
            } else {
                flush(cjkRun, word, out);
            }
        }
        flush(cjkRun, word, out);
        return out;
    }

    private static void flush(StringBuilder cjkRun, StringBuilder word, List<String> out) {
        if (word.length() > 0) {
            out.add(word.toString().toLowerCase());
            word.setLength(0);
        }
        if (cjkRun.length() > 0) {
            addBigrams(cjkRun, out);
            cjkRun.setLength(0);
        }
    }

    private static void addBigrams(StringBuilder run, List<String> out) {
        if (run.length() == 1) {
            return;
        }
        for (int i = 0; i + 1 < run.length(); i++) {
            out.add(run.substring(i, i + 2));
        }
    }

    private static Map<String, Integer> termFreq(List<String> terms) {
        Map<String, Integer> tf = new HashMap<>();
        for (String t : terms) {
            tf.merge(t, 1, Integer::sum);
        }
        return tf;
    }

    private static boolean isCjk(char c) {
        return (c >= 0x4e00 && c <= 0x9fff)      // 基本汉字
                || (c >= 0x3400 && c <= 0x4dbf) // 扩展 A
                || (c >= 0xf900 && c <= 0xfaff); // 兼容表意
    }

    /** 只保留有内容的 token 集合，供测试断言切分口径 */
    public static Set<String> vocabulary(String text) {
        return new LinkedHashSet<>(tokenize(text));
    }
}