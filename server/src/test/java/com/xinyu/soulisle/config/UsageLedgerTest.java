package com.xinyu.soulisle.config;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.temporal.ChronoUnit;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * r130：成本**总量闸**的判据。
 *
 * <p>关键设计前提：时钟可注入 ⇒ 「跨日重置」这条最容易被跳过不测的腿，
 * 在本仓能被真验（不需要 sleep 到第二天，也不需要靠改系统时间）。
 */
class UsageLedgerTest {

    /** 可推进的时钟：跨日腿唯一的正解（fixed 时钟无法验重置） */
    static final class MutableClock extends Clock {
        private Instant now;
        private final ZoneId zone;

        MutableClock(String isoLocalDateTime) {
            this.zone = ZoneId.systemDefault();
            this.now = LocalDateTime.parse(isoLocalDateTime).atZone(zone).toInstant();
        }

        void advanceDays(int days) {
            now = now.plus(days, ChronoUnit.DAYS);
        }

        @Override
        public ZoneId getZone() {
            return zone;
        }

        @Override
        public Clock withZone(ZoneId z) {
            return this;
        }

        @Override
        public Instant instant() {
            return now;
        }
    }

    private static UsageLedger ledger(Clock clock, long requestLimit, long tokenLimit) {
        return new UsageLedger(clock, requestLimit, tokenLimit);
    }

    @Test
    @DisplayName("未达日额时放行，并如实累计")
    void allowsAndCounts() {
        UsageLedger l = ledger(new MutableClock("2026-10-12T10:00:00"), 5, 0);
        UsageLedger.Verdict v = l.acquire(10);
        assertTrue(v.allowed(), "第一次必须放行");
        assertEquals(1, v.used());
        assertEquals(1, l.rawRequests());
    }

    @Test
    @DisplayName("恰好用满日额的那一次放行，下一次拒绝（边界语义是「允许 N 次」不是「允许 N-1 次」）")
    void boundaryIsInclusive() {
        UsageLedger l = ledger(new MutableClock("2026-10-12T10:00:00"), 3, 0);
        assertTrue(l.acquire(0).allowed());
        assertTrue(l.acquire(0).allowed());
        assertTrue(l.acquire(0).allowed(), "第 3 次（等于限额）必须放行");
        UsageLedger.Verdict fourth = l.acquire(0);
        assertFalse(fourth.allowed(), "第 4 次必须拒绝");
        assertEquals(3, fourth.used(), "拒绝时 used 回传的是满额累计，不是 0");
        assertEquals(3, l.rawRequests(), "被拒绝的那次不得计入用量，否则越重试越早锁死");
    }

    @Test
    @DisplayName("限额配 0 = 不限：连打 500 次全放行")
    void zeroMeansUnlimited() {
        UsageLedger l = ledger(new MutableClock("2026-10-12T10:00:00"), 0, 0);
        for (int i = 0; i < 500; i++) {
            assertTrue(l.acquire(1).allowed(), "第 " + i + " 次不应被拦");
        }
        assertEquals(500, l.rawRequests());
    }

    @Test
    @DisplayName("跨日自动重置：昨天打满，今天重新有额度")
    void resetsAcrossDays() {
        MutableClock clock = new MutableClock("2026-10-12T10:00:00");
        UsageLedger l = ledger(clock, 2, 0);
        assertTrue(l.acquire(0).allowed());
        assertTrue(l.acquire(0).allowed());
        assertFalse(l.acquire(0).allowed(), "当天第三次应被拒");

        clock.advanceDays(1);
        UsageLedger.Verdict next = l.acquire(0);
        assertTrue(next.allowed(), "跨日后必须重新放行");
        assertEquals(1, l.rawRequests(), "跨日后计数必须从 1 重新开始");
        assertEquals("2026-10-13", l.snapshot().day());
    }

    @Test
    @DisplayName("token 维独立判：本次会把累计顶过上限就拒绝，且本次不计入")
    void tokenDimensionIndependent() {
        UsageLedger l = ledger(new MutableClock("2026-10-12T10:00:00"), 0, 10);
        assertTrue(l.acquire(6).allowed(), "累计 6 ≤ 10 放行");
        assertFalse(l.acquire(6).allowed(), "再来 6 会到 12 > 10 ⇒ 拒绝");
        assertTrue(l.acquire(4).allowed(), "4 恰好填满 10 应放行");
        assertEquals(10, l.snapshot().tokens(), "被拒的那次不得把累计顶上去");
        assertEquals(2, l.rawRequests(), "两次放行 + 一次拒绝 ⇒ 计数值是 2");
    }

    @Test
    @DisplayName("负数估算按 0 记：防御上游给出负长度，不让台账被减成负数")
    void negativeEstimateClamped() {
        UsageLedger l = ledger(new MutableClock("2026-10-12T10:00:00"), 0, 0);
        l.acquire(-999);
        assertEquals(0, l.snapshot().tokens());
        assertEquals(0, UsageLedger.estimateTokens(-1));
        assertEquals(0, UsageLedger.estimateTokens(0));
        assertEquals(100, UsageLedger.estimateTokens(400));
    }

    @Test
    @DisplayName("拒绝时给出到次日零点的 Retry-After，且至少 1 秒")
    void retryAfterIsSane() {
        UsageLedger l = ledger(new MutableClock("2026-10-12T23:59:59"), 1, 0);
        l.acquire(0);
        UsageLedger.Verdict denied = l.acquire(0);
        assertFalse(denied.allowed());
        assertTrue(denied.retryAfterSeconds() >= 1, "Retry-After 至少 1 秒，不能给 0 让客户端死循环");
        assertTrue(denied.retryAfterSeconds() <= 2, "距零点 1 秒时应给 1~2 秒");
    }

    @Test
    @DisplayName("快照回传限额与用量，供 /api/usage 读数")
    void snapshotCarriesLimits() {
        UsageLedger l = ledger(new MutableClock("2026-10-12T10:00:00"), 7, 9);
        l.acquire(4);
        UsageLedger.Snapshot s = l.snapshot();
        assertEquals("2026-10-12", s.day());
        assertEquals(1, s.requests());
        assertEquals(4, s.tokens());
        assertEquals(7, s.requestLimit());
        assertEquals(9, s.tokenLimit());
    }

    @Test
    @DisplayName("并发下计数不丢：10 线程 × 20 次 = 200")
    void concurrentAccountingIsExact() throws Exception {
        UsageLedger l = ledger(new MutableClock("2026-10-12T10:00:00"), 0, 0);
        int threads = 10;
        int per = 20;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch ready = new CountDownLatch(threads);
        CountDownLatch done = new CountDownLatch(threads);
        try {
            for (int t = 0; t < threads; t++) {
                pool.submit(() -> {
                    ready.countDown();
                    try {
                        ready.await(2, TimeUnit.SECONDS);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    }
                    for (int i = 0; i < per; i++) {
                        l.acquire(1);
                    }
                    done.countDown();
                });
            }
            assertTrue(done.await(5, TimeUnit.SECONDS), "并发腿不该挂住");
        } finally {
            pool.shutdownNow();
        }
        assertEquals(threads * per, l.rawRequests(), "这里争用的是钱，计数丢一个就是账不平");
    }
}
