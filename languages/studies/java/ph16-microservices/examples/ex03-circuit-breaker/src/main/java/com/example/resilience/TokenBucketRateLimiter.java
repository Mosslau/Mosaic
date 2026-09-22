package com.example.resilience;

import java.time.Clock;

/**
 * 令牌桶限流器：桶以固定速率补令牌，请求取走令牌，无令牌则拒绝。
 * 与「漏桶」（匀速流出、削峰）相对：令牌桶允许不超过桶容量的突发（burst）。
 * Sentinel 的匀速排队/突发限流、Gateway 的 RequestRateLimiter 底层都是这类算法（见主文档 3.3）。
 */
public class TokenBucketRateLimiter {

    private final long capacity;
    private final double refillPerMillis;
    private final Clock clock;

    private double tokens;
    private long lastRefillMillis;

    public TokenBucketRateLimiter(long capacity, double tokensPerSecond, Clock clock) {
        this.capacity = capacity;
        this.refillPerMillis = tokensPerSecond / 1000.0;
        this.clock = clock;
        this.tokens = capacity;
        this.lastRefillMillis = clock.millis();
    }

    /** 尝试取 1 个令牌；取到返回 true，否则 false（调用方据此放行或 429） */
    public synchronized boolean tryAcquire() {
        refill();
        if (tokens >= 1.0) {
            tokens -= 1.0;
            return true;
        }
        return false;
    }

    public synchronized double availableTokens() {
        refill();
        return tokens;
    }

    private void refill() {
        long now = clock.millis();
        long elapsed = now - lastRefillMillis;
        if (elapsed > 0) {
            tokens = Math.min(capacity, tokens + elapsed * refillPerMillis);
            lastRefillMillis = now;
        }
    }
}
