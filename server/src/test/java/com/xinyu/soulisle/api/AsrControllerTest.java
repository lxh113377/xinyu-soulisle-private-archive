package com.xinyu.soulisle.api;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * r187 补齐：AsrController（jacoco LINE 13.5%、BRANCH 0%）的直测。
 *
 * <p>不起 Spring 上下文（Controller 是纯构造注入，@Value 只是默认值来源），
 * 直接 new —— 与既有 controller 测试同口径：快、无端口、无上下文启动税。
 * 桩打在 AsrProxy 不可（它是 final 字段真 new），故 enabled=false / 空音频
 * / 未知方言回落这三组分支用真构造参数走；上游交互已在 AsrProxyTest 覆盖。
 */
class AsrControllerTest {

    private AsrController ctl(boolean enabled) {
        // url 指向无人监听的回环端口即可：enabled=false 时根本不会发请求（零探测红线）
        return new AsrController("http://127.0.0.1:1", 1000, enabled);
    }

    @Test
    @DisplayName("status()：enabled/ready/dialects/vocab 四键齐全，方言表含八码")
    void statusShape() {
        Map<String, Object> m = ctl(false).status();
        assertEquals(false, m.get("enabled"));
        assertEquals(false, m.get("ready"));
        assertEquals(true, m.get("vocab"));
        @SuppressWarnings("unchecked")
        java.util.Set<String> ds = (java.util.Set<String>) m.get("dialects");
        assertEquals(8, ds.size());
        assertTrue(ds.containsAll(java.util.List.of("mandarin", "yue", "chuan", "wu",
                "dongbei", "minnan", "teochew", "en")));
    }

    @Test
    @DisplayName("默认态（enabled=false）：transcribe 必 503 asr-disabled，不得伪装在线")
    void disabledReturns503WithErrorCode() {
        ResponseEntity<Map<String, Object>> r = ctl(false)
                .transcribe("mandarin", null, "wav".getBytes());
        assertEquals(503, r.getStatusCode().value());
        assertEquals("asr-disabled", r.getBody().get("error"));
        assertEquals("xinyu.asr.enabled=false", r.getBody().get("detail"));
    }

    @Test
    @DisplayName("空音频 ⇒ 400 empty-audio（先于上游判断，不达代理）")
    void emptyAudioReturns400() {
        ResponseEntity<Map<String, Object>> r = ctl(true).transcribe("mandarin", null, new byte[0]);
        assertEquals(400, r.getStatusCode().value());
        assertEquals("empty-audio", r.getBody().get("error"));
        r = ctl(true).transcribe("mandarin", null, null);
        assertEquals(400, r.getStatusCode().value());
    }

    @Test
    @DisplayName("enabled 但上游不可达 ⇒ 503 asr-unavailable，body 带 bytes 供前端如实显示")
    void unreachableUpstreamReturns503() {
        ResponseEntity<Map<String, Object>> r = ctl(true)
                .transcribe("mandarin", null, "wav".getBytes());
        assertEquals(503, r.getStatusCode().value());
        assertEquals("asr-unavailable", r.getBody().get("error"));
        assertEquals("mandarin", r.getBody().get("dialect"));
        assertEquals(3, r.getBody().get("bytes"));
    }

    @Test
    @DisplayName("未知方言 ⇒ 回落 mandarin（脏值不透传引擎，与前端 asr-local.js 同口径）")
    void unknownDialectFallsBackToMandarin() {
        ResponseEntity<Map<String, Object>> r = ctl(true)
                .transcribe("not_a_dialect", null, "wav".getBytes());
        assertEquals(503, r.getStatusCode().value());
        assertEquals("asr-unavailable", r.getBody().get("error"));
        assertEquals("mandarin", r.getBody().get("dialect"));
    }
}
