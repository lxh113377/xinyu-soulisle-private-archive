package com.xinyu.soulisle.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.xinyu.soulisle.config.QuotaFilter;
import com.xinyu.soulisle.config.UsageLedger;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 用量读数（r130 新增）：把「今天花了多少」这件事从黑盒变成可查询的数。
 *
 * <p><b>为什么必须有个端点</b>：{@code X-Quota-Day-Used} 响应头只能被发起方自己看到，
 * 而排障时最常见的问题恰恰是「到底是谁、从什么时候开始把额度打满的」——
 * 那需要能不打钱就问一句现在用了多少。对标 {@code lobe-chat} 的 usage ledger 同样
 * 有可读的用量面（burn-down 曲线与耗尽预测），本仓先做到「能读」这一格。
 *
 * <p><b>为什么敢裸奔（不额外鉴权）</b>：本端点<b>只回计数</b>，不含请求体、响应体、
 * 会话内容、密钥或客户端标识 —— 泄漏面只有「今天被调用了几次」，
 * 而这本身也是健康检查式的信息。若部署形态要求收口，配置 {@code xinyu.api-token} 即可
 * （{@code ApiTokenFilter} 覆盖所有 {@code /api/**}）。
 */
@RestController
public class UsageController {

    private final ObjectMapper mapper = new ObjectMapper();
    private final QuotaFilter quota;

    public UsageController(QuotaFilter quota) {
        this.quota = quota;
    }

    @GetMapping("/api/usage")
    public ResponseEntity<byte[]> usage() {
        UsageLedger.Snapshot s = quota.snapshot();
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("day", s.day());
        body.put("requests", s.requests());
        body.put("tokens", s.tokens());
        body.put("requestLimit", s.requestLimit());
        body.put("tokenLimit", s.tokenLimit());
        // 显式标注：token 是字节数/4 的折算，不是上游计费口径 —— 免得后人拿它去对账账单
        body.put("tokensAreEstimated", true);
        return ResponseEntity.status(200)
                .contentType(MediaType.APPLICATION_JSON)
                .body(write(body).getBytes(StandardCharsets.UTF_8));
    }

    private String write(Object o) {
        try {
            return mapper.writeValueAsString(o);
        } catch (Exception e) {
            return "{\"error\":\"serialize\"}";
        }
    }
}
