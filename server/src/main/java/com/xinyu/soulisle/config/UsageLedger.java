package com.xinyu.soulisle.config;

import java.time.Clock;
import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 成本面**总量闸**（r130 新增）：按自然日累计调用量与估算 token，超日额即熔断。
 *
 * <p><b>为什么在 r128 的瞬时闸之外还要这一道</b>：{@link ApiGuardFilter} 的令牌桶只堵
 * 「单位时间内来得快」。一个每分钟只打 1 次的脚本既填不满桶、又能 24 小时不间断烧上游额度 ——
 * 也就是<b>限流防不住慢速白嫖</b>。对标面上 {@code lobe-chat} 的 usage ledger 同时给
 * 会话窗口与日/周窗口两级限额，r128 只落地了前者这一半，本类补齐后者。
 *
 * <p><b>为什么是「估算」token</b>：上游真实用量只在响应里回，且流式响应没有 usage 段。
 * 这里用请求体字节数的粗略折算（{@link #estimateTokens(long)}）做**数量级护栏**，
 * 不冒充精确计费；因此 {@code daily-token-limit} 默认配成 0（不限），
 * 只有在愿意接受估算误差时才打开。
 *
 * <p><b>并发语义</b>：{@link #acquire(long)} 整体 synchronized。临界区只有几次算术，
 * 而这里争用的是「钱」，正确性优先于吞吐；真到了每秒几千次 chat 的量级，
 * 本仓单体部署形态早已是别的瓶颈。
 *
 * <p><b>时钟可注入</b>：构造参数带 {@link Clock}，测试用固定时钟验证「跨日重置」，
 * 不需要 sleep 到第二天 —— 这一条是本类能被单测覆盖的前提。
 */
public class UsageLedger {

    /** 一次取用结果：{@code allowed=false} 时给出建议的重试秒数（到次日零点） */
    public record Verdict(boolean allowed, long used, long limit, long retryAfterSeconds) {}

    /** 当前用量快照：供 {@code /api/usage} 与排障读数，不含任何请求/响应内容 */
    public record Snapshot(String day, long requests, long tokens, long requestLimit, long tokenLimit) {}

    private final Clock clock;
    private final long requestLimit;
    private final long tokenLimit;

    private final AtomicLong requests = new AtomicLong();
    private final AtomicLong tokens = new AtomicLong();
    private volatile LocalDate day;

    /**
     * @param clock        时钟（跨日判定与 Retry-After 都用它，测试可注入固定时钟）
     * @param requestLimit 每日请求数上限；{@code <=0} = 不限
     * @param tokenLimit   每日估算 token 上限；{@code <=0} = 不限
     */
    public UsageLedger(Clock clock, long requestLimit, long tokenLimit) {
        this.clock = clock == null ? Clock.systemDefaultZone() : clock;
        this.requestLimit = requestLimit <= 0 ? 0 : requestLimit;
        this.tokenLimit = tokenLimit <= 0 ? 0 : tokenLimit;
        this.day = LocalDate.now(this.clock);
    }

    /**
     * 记一次调用并判定是否放行。
     *
     * <p>两维各自独立判：请求数到了、或本次会把累计 token 顶过上限，都拒绝。
     * 被拒绝的那一次<b>不计入用量</b>（先加后回滚），否则「重试一次就又少一个名额」，
     * 客户端会越重试越早被锁死。
     */
    public synchronized Verdict acquire(long tokenEstimate) {
        rollover();
        long est = Math.max(0, tokenEstimate);

        long usedRequests = requests.get();
        if (requestLimit > 0 && usedRequests >= requestLimit) {
            return new Verdict(false, usedRequests, requestLimit, secondsUntilTomorrow());
        }
        if (tokenLimit > 0 && tokens.get() + est > tokenLimit) {
            return new Verdict(false, usedRequests, requestLimit, secondsUntilTomorrow());
        }

        requests.incrementAndGet();
        tokens.addAndGet(est);
        return new Verdict(true, requests.get(), requestLimit, 0);
    }

    /** 只读快照（不判限额、不改状态） */
    public Snapshot snapshot() {
        return new Snapshot(day.toString(), requests.get(), tokens.get(), requestLimit, tokenLimit);
    }

    /** 供测试断言「跨日确实重置了」：不暴露给业务路径 */
    long rawRequests() {
        return requests.get();
    }

    /**
     * 字节数 → 粗略 token 折算。
     *
     * <p>⚠️ 这是<b>数量级估算不是计费口径</b>：中文按 UTF-8 通常 1~1.5 token/字，
     * 英文约 4 字节/token。取「字节数/4」只为拿到一个与请求规模单调相关的量，
     * 让「今天到底打出去多少」这台账有个能聚合的维度。
     */
    public static long estimateTokens(long bytes) {
        return bytes <= 0 ? 0 : bytes / 4;
    }

    private void rollover() {
        LocalDate today = LocalDate.now(clock);
        if (!today.equals(day)) {
            day = today;
            requests.set(0);
            tokens.set(0);
        }
    }

    /** 距次日零点的秒数（Retry-After 用）；固定时钟下也不会返回 0 */
    private long secondsUntilTomorrow() {
        LocalDateTime now = LocalDateTime.now(clock);
        LocalDateTime midnight = now.toLocalDate().plusDays(1).atStartOfDay();
        long seconds = Duration.between(now, midnight).getSeconds();
        return Math.max(1, seconds);
    }
}
