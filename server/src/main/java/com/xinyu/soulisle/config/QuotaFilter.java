package com.xinyu.soulisle.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.util.LinkedHashSet;
import java.util.Set;

/**
 * 成本面**总量闸**的横切接线（r130 新增），读数是 {@link UsageLedger}。
 *
 * <p>与 {@link ApiGuardFilter}（瞬时令牌桶）的关系：两道闸互补，不是重复。
 * 令牌桶挡「突发」，按日台账挡「慢速持续」；后者正是前者结构上挡不住的形态
 * （每分钟 1 次永远填不满桶，却能一天打满 1440 次）。
 *
 * <p><b>默认只计量 {@code /api/chat}</b>：全仓唯一真花钱的端点就是它。
 * 情绪识别走本地词典（危机短路后连 LLM 都不调），记忆读写只是本地库 ——
 * 把它们也计入日额会平白吃掉演示期的正常调用预算。
 *
 * <p><b>契约不破</b>：与 r128 的闸同族 —— 只可能新增 {@code 429} 与三个响应头，
 * <b>绝不改动</b>既有的 {@code 200}/{@code 4xx}/{@code 5xx} 响应体。
 */
@Component
@Order(25)
public class QuotaFilter extends OncePerRequestFilter {

    private final boolean enabled;
    private final Set<String> meteredPaths;
    private final UsageLedger ledger;

    // ⚠️ @Autowired 不能省：本类有两个构造器（这一个 + 下面可注入台账的装配用构造器），
    // 不标注的话 Spring 会去找「默认构造器」而我们没有 ⇒ 启动期直接失败（r130 实测踩到）。
    @Autowired
    public QuotaFilter(@Value("${xinyu.quota.enabled:true}") boolean enabled,
                       @Value("${xinyu.quota.paths:/api/chat}") String paths,
                       @Value("${xinyu.quota.daily-requests:2000}") long dailyRequests,
                       @Value("${xinyu.quota.daily-tokens:0}") long dailyTokens) {
        this(enabled, parsePaths(paths), new UsageLedger(Clock.systemDefaultZone(), dailyRequests, dailyTokens));
    }

    /**
     * 装配用构造器：可直接注入带固定时钟的台账，不需要等真实跨日才能验「跨日重置」。
     * public 是因为 {@code api} 包的 {@code /api/usage} 控制器也要按此形态装配。
     */
    public QuotaFilter(boolean enabled, Set<String> meteredPaths, UsageLedger ledger) {
        this.enabled = enabled;
        this.meteredPaths = meteredPaths;
        this.ledger = ledger;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !request.getRequestURI().startsWith("/api/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String path = request.getRequestURI();
        if (!enabled || !meteredPaths.contains(path)) {
            chain.doFilter(request, response);
            return;
        }

        UsageLedger.Verdict verdict = ledger.acquire(UsageLedger.estimateTokens(declaredLength(request)));
        // 放行时 used 含本次；拒绝时 used 是「满额那一刻」的累计 —— 两者都如实给，不粉饰
        response.setHeader("X-Quota-Day-Used", String.valueOf(verdict.used()));
        if (verdict.limit() > 0) {
            response.setHeader("X-Quota-Day-Limit", String.valueOf(verdict.limit()));
        }
        if (!verdict.allowed()) {
            response.setHeader("Retry-After", String.valueOf(verdict.retryAfterSeconds()));
            writeJson(response, 429, "{\"error\":\"daily-quota-exceeded\"}");
            return;
        }
        chain.doFilter(request, response);
    }

    /** 当前用量快照（供 {@code /api/usage} 读数）；跨包给控制器用，故 public，但只读不改状态 */
    public UsageLedger.Snapshot snapshot() {
        return ledger.snapshot();
    }

    /** 逗号分隔的路径清单；空串 ⇒ 空集（一个都不计量，等同于只留读数） */
    static Set<String> parsePaths(String raw) {
        Set<String> out = new LinkedHashSet<>();
        if (raw == null || raw.isBlank()) {
            return out;
        }
        for (String part : raw.split(",")) {
            String p = part.trim();
            if (!p.isEmpty()) {
                out.add(p);
            }
        }
        return out;
    }

    /** chunked（无 Content-Length）时返回 -1 ⇒ 折算成 0 token，不阻塞业务 */
    static long declaredLength(HttpServletRequest request) {
        String raw = request.getHeader("Content-Length");
        if (raw == null || raw.isBlank()) {
            return -1L;
        }
        try {
            return Long.parseLong(raw.trim());
        } catch (NumberFormatException e) {
            return -1L;
        }
    }

    private void writeJson(HttpServletResponse response, int status, String body) throws IOException {
        byte[] data = body.getBytes(StandardCharsets.UTF_8);
        response.setStatus(status);
        response.setContentType("application/json");
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setContentLength(data.length);
        response.getOutputStream().write(data);
    }
}
