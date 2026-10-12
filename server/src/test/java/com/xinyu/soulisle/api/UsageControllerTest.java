package com.xinyu.soulisle.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xinyu.soulisle.config.QuotaFilter;
import com.xinyu.soulisle.config.UsageLedger;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.ResponseEntity;

import java.time.Clock;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * r130：用量读数端点判据。最要紧的一条不是"能返回"，而是
 * **这个端点不得泄漏任何请求/响应内容** —— 它是一个无需额外鉴权就能打的只读端点。
 */
class UsageControllerTest {

    private static JsonNode read(ResponseEntity<byte[]> resp) throws Exception {
        return new ObjectMapper().readTree(resp.getBody());
    }

    @Test
    @DisplayName("回传五个数与两个限额，并显式标注 token 是估算值")
    void returnsCountersAndLimits() throws Exception {
        QuotaFilter quota = new QuotaFilter(true, "/api/chat", 50, 0);
        UsageController c = new UsageController(quota);

        ResponseEntity<byte[]> resp = c.usage();
        JsonNode n = read(resp);

        assertEquals(200, resp.getStatusCode().value());
        assertEquals(0, n.get("requests").asInt());
        assertEquals(0, n.get("tokens").asInt());
        assertEquals(50, n.get("requestLimit").asInt());
        assertEquals(0, n.get("tokenLimit").asInt());
        assertTrue(n.get("tokensAreEstimated").asBoolean(), "必须显式标注估算，防止后人拿它去对账账单");
        assertTrue(n.get("day").asText().matches("\\d{4}-\\d{2}-\\d{2}"));
    }

    @Test
    @DisplayName("读数反映真实累计：打两次就是 2（不是恒 0 的摆设端点）")
    void reflectsRealUsage() throws Exception {
        UsageLedger ledger = new UsageLedger(Clock.systemDefaultZone(), 50, 0);
        QuotaFilter quota = new QuotaFilter(true, Set.of("/api/chat"), ledger);
        // 显式走「字节 → token」折算：acquire 收的是 token 数，直接传字节会把折算链路绕过
        long perCall = UsageLedger.estimateTokens(400);   // 400 字节 ⇒ 100 token
        ledger.acquire(perCall);
        ledger.acquire(perCall);
        UsageController c = new UsageController(quota);

        JsonNode n = read(c.usage());

        assertEquals(2, n.get("requests").asInt());
        assertEquals(200, n.get("tokens").asInt(), "两次 ×100 token = 200");
    }

    @Test
    @DisplayName("读数端点本身不耗额度：它不在计量清单里，也不得把自己算进去")
    void readingIsFree() throws Exception {
        UsageLedger ledger = new UsageLedger(Clock.systemDefaultZone(), 50, 0);
        QuotaFilter quota = new QuotaFilter(true, Set.of("/api/chat"), ledger);
        UsageController c = new UsageController(quota);

        read(c.usage());
        read(c.usage());

        assertEquals(0, ledger.snapshot().requests(), "查用量不该花用量");
        assertFalse(quota.snapshot().day().isEmpty());
    }
}
