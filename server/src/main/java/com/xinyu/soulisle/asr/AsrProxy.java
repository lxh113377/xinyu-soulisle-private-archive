package com.xinyu.soulisle.asr;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

/**
 * 本机 ASR 代理（J6）：把一段 WAV 转发给本机 Python 推理服务，拿回转写文本。
 *
 * <p><b>为什么单独一个 Python 进程</b>：模型是 PyTorch 生态（transformers + peft），
 * Java 侧只能通过 HTTP 调；而模型常驻显存（实测加载 1.9~2.2s），
 * 每请求重载一次在交互上是不可接受的。故 Java 侧只做转发，沿用
 * {@code llm/LlmProxy} 的 JDK 内置 HttpClient 模式，<b>零新增依赖</b>。
 *
 * <p><b>失败口径（本项目红线：不得伪装在线）</b>：
 * 本类<b>永不抛异常、永不返回占位文本</b>。Python 服务不可达 / 超时 / 返 503 时，
 * 一律返回 {@code ok=false}，由 {@code AsrController} 返 HTTP 503，
 * 前端据此回落到 Web Speech。任何时候都不会出现「识别失败但返回一句编出来的话」。
 *
 * <p><b>方言与 language 参数的真实约束（实测，别再猜）</b>：
 * Qwen3-ASR-0.6B 的 transformers 实现<b>只有 {@code LANGUAGE_CODE_TO_NAME}，没有方言接口</b>。
 * 传 {@code "Sichuan"} / {@code "Dongbei"} / {@code "Wu"} / {@code "Minnan"} 会直接
 * {@code ValueError: Unsupported language}。**只有粤语能用 {@code yue} 强制**，
 * 其余方言只能走自动识别。故本类对 chuan/wu/dongbei/minnan 一律传 dialect 但<b>不传 language</b>。
 */
public class AsrProxy {

    /** 转写结果。ok=false 时 text 恒为空串，绝不携带任何编造内容。 */
    public record Result(boolean ok, String text, String dialect, String engine,
                         long inferMs, Double rtf, String err) {
        public static Result fail(String err) {
            return new Result(false, "", "", "", 0L, null, err);
        }
    }

    private final HttpClient http;
    private final ObjectMapper mapper = new ObjectMapper();
    private final URI base;
    private final Duration timeout;
    private final boolean enabled;

    public AsrProxy(String url, int timeoutMs, boolean enabled) {
        this.enabled = enabled;
        String u = (url == null || url.isBlank()) ? "http://127.0.0.1:8765" : url;
        while (u.endsWith("/")) {
            u = u.substring(0, u.length() - 1);
        }
        this.base = URI.create(u);
        this.timeout = Duration.ofMillis(timeoutMs <= 0 ? 15000 : timeoutMs);
        this.http = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(3))   // 连不上要**快**回落，不能占住通话线程
                .build();
    }

    public boolean enabled() {
        return enabled;
    }

    /**
     * 探针：Python 服务是否就绪。供前端「显式开启」路径用；
     * 默认态不调用（对应 C15「默认态零探测」的公网红线）。
     */
    public boolean ready() {
        if (!enabled) {
            return false;
        }
        try {
            HttpRequest req = HttpRequest.newBuilder(base.resolve("/health"))
                    .timeout(Duration.ofSeconds(2))
                    .GET().build();
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
            if (resp.statusCode() / 100 != 2) {
                return false;
            }
            JsonNode n = mapper.readTree(resp.body());
            return n.path("ready").asBoolean(false);
        } catch (Exception e) {
            return false;
        }
    }

    /**
     * 转写一段 WAV（16kHz / 16bit / 单声道 PCM）。
     *
     * @param wav     原始 WAV 字节
     * @param dialect 方言码（mandarin/yue/chuan/wu/dongbei/minnan/teochew/en）
     * @return 永不为 null；失败时 ok=false
     */
    public Result transcribe(byte[] wav, String dialect) {
        return transcribe(wav, dialect, null);
    }

    /**
     * @param vocab "off" 表示显式关闭领域热词；null 表示用服务端默认词表。
     *              ⚠ 自定义词表**不从公网请求接收**（长度不受控，且等于让调用方
     *              往识别管线里塞任意偏置）。要换词表改服务端配置或内部调用方。
     */
    public Result transcribe(byte[] wav, String dialect, String vocab) {
        if (!enabled) {
            return Result.fail("asr-disabled");
        }
        if (wav == null || wav.length == 0) {
            return Result.fail("empty-audio");
        }
        String d = (dialect == null || dialect.isBlank()) ? "mandarin" : dialect;
        try {
            StringBuilder q = new StringBuilder("/transcribe?dialect=").append(enc(d));
            if ("off".equalsIgnoreCase(vocab)) {
                q.append("&vocab=off");
            }
            HttpRequest req = HttpRequest.newBuilder(base.resolve(q.toString()))
                    .timeout(timeout)
                    .header("Content-Type", "audio/wav")
                    .POST(HttpRequest.BodyPublishers.ofByteArray(wav))
                    .build();
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
            String body = resp.body();

            if (resp.statusCode() / 100 != 2) {
                // 把上游的 error 码带出来，便于前端分辨「服务没起」与「音频不合法」
                String code = "upstream-" + resp.statusCode();
                try {
                    JsonNode n = mapper.readTree(body);
                    if (n.hasNonNull("error")) {
                        code = n.get("error").asText();
                    }
                } catch (Exception ignore) {
                    // 非 JSON 错误体，用状态码顶上
                }
                return Result.fail(code);
            }
            JsonNode n = mapper.readTree(body);
            return new Result(true,
                    n.path("text").asText(""),
                    n.path("dialect").asText(d),
                    n.path("engine").asText(""),
                    n.path("inferMs").asLong(0L),
                    n.hasNonNull("rtf") ? n.get("rtf").asDouble() : null,
                    null);
        } catch (java.net.http.HttpTimeoutException e) {
            return Result.fail("asr-timeout");
        } catch (Exception e) {
            // 连不上（服务没起/端口不通）—— 这是最常见的降级触发条件
            return Result.fail("asr-unavailable");
        }
    }

    private static String enc(String s) {
        try {
            return java.net.URLEncoder.encode(s, StandardCharsets.UTF_8);
        } catch (Exception e) {
            return "mandarin";
        }
    }
}