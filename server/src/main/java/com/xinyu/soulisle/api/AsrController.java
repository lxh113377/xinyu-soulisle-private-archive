package com.xinyu.soulisle.api;

import com.xinyu.soulisle.asr.AsrProxy;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/**
 * 本机 ASR 端点（J6）：把前端录好的一段语音转成文字。
 *
 * <p><b>契约</b>
 * <ul>
 *   <li>{@code POST /api/asr}，请求体是原始 WAV 字节（{@code Content-Type: audio/wav}），
 *       方言走查询参数 {@code ?dialect=…}（默认 mandarin）。</li>
 *   <li>成功：200 {@code {text, dialect, engine, inferMs, audioSeconds, rtf, source:"local"}}</li>
 *   <li>失败：503 {@code {error:"asr-unavailable"|"asr-timeout"|…, detail}} —— 前端据此
 *       <b>回落 Web Speech</b>。绝不返回占位文本（红线：不得伪装在线）。</li>
 * </ul>
 *
 * <p><b>为什么是原始字节而不是 multipart</b>：前端侧要把 Float32 PCM 打成 WAV，
 * 走裸 body 最省一层编码与服务端解析；Spring 直接 {@code @RequestBody byte[]} 即可。
 *
 * <p><b>体上限沿用既有闸</b>：{@code xinyu.guard.max-body-bytes} 默认 256 KiB，
 * 16kHz/16bit 单声道 = 32 KB/s ⇒ 约 8 秒。前端已把单次语音截到 6s（见 asr-local.js），
 * 故不必为此单独放宽全局闸 —— 放宽全局闸会影响所有 /api/** 的内存面防护。
 */
@RestController
@RequestMapping("/api/asr")
public class AsrController {

    /** 与前端 asr-local.js 的 DIALECTS 保持一致；未登记的一律回落 mandarin。 */
    private static final Set<String> DIALECTS =
            Set.of("mandarin", "yue", "chuan", "wu", "dongbei", "minnan", "teochew", "en");

    private final AsrProxy proxy;

    public AsrController(@Value("${xinyu.asr.url:http://127.0.0.1:8765}") String url,
                         @Value("${xinyu.asr.timeout-ms:15000}") int timeoutMs,
                         @Value("${xinyu.asr.enabled:false}") boolean enabled) {
        this.proxy = new AsrProxy(url, timeoutMs, enabled);
    }

    /** 探针：给前端「显式开启本机引擎」时确认服务在不在。默认态不调（对应 C15 零探测红线）。 */
    @GetMapping("/status")
    public Map<String, Object> status() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("enabled", proxy.enabled());
        m.put("ready", proxy.ready());
        m.put("dialects", DIALECTS);
        m.put("vocab", true);          // 领域热词偏置默认开着（零训练成本的方言专名纠偏）
        return m;
    }

    @PostMapping(consumes = {MediaType.ALL_VALUE}, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> transcribe(
            @RequestParam(name = "dialect", defaultValue = "mandarin") String dialect,
            @RequestParam(name = "vocab", required = false) String vocab,
            @RequestBody(required = false) byte[] audio) {

        Map<String, Object> err = new LinkedHashMap<>();
        if (!proxy.enabled()) {
            err.put("error", "asr-disabled");
            err.put("detail", "xinyu.asr.enabled=false");
            return ResponseEntity.status(503).body(err);
        }
        if (audio == null || audio.length == 0) {
            err.put("error", "empty-audio");
            return ResponseEntity.status(400).body(err);
        }
        String d = DIALECTS.contains(dialect) ? dialect : "mandarin";
        // vocab 不往前端暴露自定义值会变成长度不受控的查询串；只认 off / 缺省。
        // 自定义词表走服务端配置或内部调用方，不开放给公网请求。
        String v = "off".equalsIgnoreCase(vocab) ? "off" : null;

        AsrProxy.Result r = proxy.transcribe(audio, d, v);
        if (!r.ok()) {
            err.put("error", r.err());
            err.put("dialect", d);
            err.put("bytes", audio.length);
            return ResponseEntity.status(503).body(err);
        }
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("text", r.text());
        m.put("dialect", r.dialect());
        m.put("engine", r.engine());
        m.put("inferMs", r.inferMs());
        m.put("bytes", audio.length);
        m.put("rtf", r.rtf());
        m.put("vocab", !"off".equals(v));  // 是否启用了领域热词偏置，供前端如实显示
        m.put("source", "local");          // 前端据此如实显示「本机引擎」，不得伪装云端
        return ResponseEntity.ok(m);
    }
}