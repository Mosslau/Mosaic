// project/src/seckill/TokenBucket.java —— 秒杀入口限流（令牌桶）
// 教学映射：令牌桶 = 「容量限突发 + 速率限均值」，语义与 examples/ex05、exercises/sol-02 一致；
//           秒杀场景里入口限流的第一道闸：把每个用户的请求速率压到可控水位，避免网关被打满。
//           生产多实例版把桶搬进 Redis（Lua 取令牌），见主文档 3.5 —— 本 demo 是单机语义版。
package seckill;

/** 令牌桶：满桶可突发，tokensPerSecond 恒定补充（rate<=0 时只出不补，便于确定性断言） */
final class TokenBucket {
    private final Clock clock;
    private final int capacity;
    private final double tokensPerMs;
    private double tokens;
    private long lastRefill;

    TokenBucket(Clock clock, int capacity, double tokensPerSecond) {
        this.clock = clock;
        this.capacity = capacity;
        this.tokensPerMs = tokensPerSecond / 1000.0;
        this.tokens = capacity; // 初始满桶：开抢瞬间允许一整桶突发
        this.lastRefill = clock.now();
    }

    /** 放行一次返回 true；false = 被限流 */
    synchronized boolean tryAcquire() {
        long now = clock.now();
        tokens = Math.min(capacity, tokens + (now - lastRefill) * tokensPerMs);
        lastRefill = now;
        if (tokens < 1.0) {
            return false;
        }
        tokens -= 1.0;
        return true;
    }
}
