package com.example;

import com.example.resilience.CallNotPermittedException;
import com.example.resilience.CircuitBreaker;
import com.example.resilience.TokenBucketRateLimiter;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** 熔断器状态机与令牌桶的确定性单测（时间用可变 Clock 注入，无 sleep） */
class ResilienceTest {

    /** 可手动拨时间的时钟 */
    private static final class MutableClock extends Clock {
        private Instant instant = Instant.ofEpochMilli(0);

        @Override
        public ZoneId getZone() {
            return ZoneId.of("UTC");
        }

        @Override
        public Clock withZone(ZoneId zone) {
            return this;
        }

        @Override
        public Instant instant() {
            return instant;
        }

        void advanceMillis(long ms) {
            instant = instant.plusMillis(ms);
        }
    }

    private final MutableClock clock = new MutableClock();

    private CircuitBreaker newBreaker() {
        // 窗口 4、失败率 ≥50% 熔断、OPEN 持续 1s、HALF_OPEN 探测 2 次
        return new CircuitBreaker("demo", 4, 50.0, Duration.ofSeconds(1), 2, clock);
    }

    private static void failNTimes(CircuitBreaker breaker, int n) {
        for (int i = 0; i < n; i++) {
            try {
                breaker.execute(() -> {
                    throw new IllegalStateException("boom");
                });
            } catch (IllegalStateException expected) {
                // 业务异常原样抛出，熔断器只记录失败
            }
        }
    }

    @Test
    void closedStatePassesCallsThrough() {
        CircuitBreaker breaker = newBreaker();
        assertThat(breaker.state()).isEqualTo(CircuitBreaker.State.CLOSED);
        assertThat(breaker.execute(() -> "ok")).isEqualTo("ok");
    }

    @Test
    void opensWhenFailureRateReachesThreshold() {
        CircuitBreaker breaker = newBreaker();
        failNTimes(breaker, 2);                       // 窗口未满（2/4），不熔断
        assertThat(breaker.state()).isEqualTo(CircuitBreaker.State.CLOSED);
        failNTimes(breaker, 2);                       // 窗口满：4/4 失败 ≥ 50% → OPEN
        assertThat(breaker.state()).isEqualTo(CircuitBreaker.State.OPEN);
    }

    @Test
    void openStateFailsFastWithoutCallingDownstream() {
        CircuitBreaker breaker = newBreaker();
        failNTimes(breaker, 4);
        assertThat(breaker.state()).isEqualTo(CircuitBreaker.State.OPEN);
        AtomicInteger downstreamCalls = new AtomicInteger();
        assertThatThrownBy(() -> breaker.execute(downstreamCalls::incrementAndGet))
                .isInstanceOf(CallNotPermittedException.class);
        assertThat(downstreamCalls.get()).isZero();   // 快速失败：下游根本没被调用
    }

    @Test
    void halfOpenAfterWaitDurationAndClosesOnProbeSuccesses() {
        CircuitBreaker breaker = newBreaker();
        failNTimes(breaker, 4);
        assertThat(breaker.state()).isEqualTo(CircuitBreaker.State.OPEN);
        clock.advanceMillis(999);
        assertThat(breaker.state()).isEqualTo(CircuitBreaker.State.OPEN);    // 等待时间未到
        clock.advanceMillis(1);
        assertThat(breaker.state()).isEqualTo(CircuitBreaker.State.HALF_OPEN);
        breaker.execute(() -> "probe-1");
        assertThat(breaker.state()).isEqualTo(CircuitBreaker.State.HALF_OPEN); // 探测数未满
        breaker.execute(() -> "probe-2");
        assertThat(breaker.state()).isEqualTo(CircuitBreaker.State.CLOSED);    // 2 次探测全成 → 恢复
    }

    @Test
    void probeFailureReopensImmediately() {
        CircuitBreaker breaker = newBreaker();
        failNTimes(breaker, 4);
        clock.advanceMillis(1000);
        assertThat(breaker.state()).isEqualTo(CircuitBreaker.State.HALF_OPEN);
        failNTimes(breaker, 1);                       // 探测调用失败
        assertThat(breaker.state()).isEqualTo(CircuitBreaker.State.OPEN);
        // 重新计时：再过 1s 才能再次探测
        clock.advanceMillis(999);
        assertThat(breaker.state()).isEqualTo(CircuitBreaker.State.OPEN);
        clock.advanceMillis(1);
        assertThat(breaker.state()).isEqualTo(CircuitBreaker.State.HALF_OPEN);
    }

    @Test
    void tokenBucketAllowsBurstUpToCapacityThenRejects() {
        TokenBucketRateLimiter limiter = new TokenBucketRateLimiter(3, 10.0, clock);
        assertThat(limiter.tryAcquire()).isTrue();    // 突发：桶内 3 个令牌一次取空
        assertThat(limiter.tryAcquire()).isTrue();
        assertThat(limiter.tryAcquire()).isTrue();
        assertThat(limiter.tryAcquire()).isFalse();   // 桶空 → 限流拒绝
    }

    @Test
    void tokenBucketRefillsAtConfiguredRate() {
        TokenBucketRateLimiter limiter = new TokenBucketRateLimiter(3, 10.0, clock);
        limiter.tryAcquire();
        limiter.tryAcquire();
        limiter.tryAcquire();
        assertThat(limiter.tryAcquire()).isFalse();
        clock.advanceMillis(200);                     // 10 个/秒 → 200ms 补 2 个
        assertThat(limiter.tryAcquire()).isTrue();
        assertThat(limiter.tryAcquire()).isTrue();
        assertThat(limiter.tryAcquire()).isFalse();
        clock.advanceMillis(10_000);                  // 补满也不超过容量
        assertThat(limiter.availableTokens()).isEqualTo(3.0);
    }
}
