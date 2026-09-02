package com.example.resilience;

import java.time.Clock;
import java.time.Duration;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.function.Supplier;

/**
 * 熔断器（Circuit Breaker）的最小实现，语义对齐 Resilience4j：
 * CLOSED —— 正常放行，滑动窗口统计失败率，失败率超阈值 → OPEN
 * OPEN   —— 快速失败（CallNotPermittedException），不碰下游；等待 waitDuration 后 → HALF_OPEN
 * HALF_OPEN —— 放行少量探测调用，全部成功 → CLOSED，任一失败 → 回 OPEN
 *
 * 教学点：熔断器保护的是「调用方自己」——下游已经病了，继续打只会拖垮自己的线程池（见主文档 4.1）。
 */
public class CircuitBreaker {

    public enum State { CLOSED, OPEN, HALF_OPEN }

    private final String name;
    private final int windowSize;              // 滑动窗口大小（按调用次数计）
    private final double failureRateThreshold; // 失败率阈值（百分比，如 50.0）
    private final Duration waitDurationInOpen; // OPEN 状态持续时间
    private final int halfOpenProbes;          // HALF_OPEN 放行的探测调用数
    private final Clock clock;

    private final Deque<Boolean> window = new ArrayDeque<>();  // true=成功 false=失败
    private State state = State.CLOSED;
    private long openedAtMillis;
    private int halfOpenSuccesses;

    public CircuitBreaker(String name, int windowSize, double failureRateThreshold,
                          Duration waitDurationInOpen, int halfOpenProbes, Clock clock) {
        this.name = name;
        this.windowSize = windowSize;
        this.failureRateThreshold = failureRateThreshold;
        this.waitDurationInOpen = waitDurationInOpen;
        this.halfOpenProbes = halfOpenProbes;
        this.clock = clock;
    }

    public State state() {
        maybeTransitionToHalfOpen();
        return state;
    }

    public <T> T execute(Supplier<T> call) {
        maybeTransitionToHalfOpen();
        if (state == State.OPEN) {
            throw new CallNotPermittedException(name);   // 快速失败：根本不发请求
        }
        try {
            T result = call.get();
            onSuccess();
            return result;
        } catch (RuntimeException e) {
            onFailure();
            throw e;
        }
    }

    private synchronized void onSuccess() {
        if (state == State.HALF_OPEN) {
            if (++halfOpenSuccesses >= halfOpenProbes) {
                state = State.CLOSED;
                window.clear();
            }
            return;
        }
        record(true);
    }

    private synchronized void onFailure() {
        if (state == State.HALF_OPEN) {
            open();           // 探测失败 → 立刻回 OPEN
            return;
        }
        record(false);
    }

    private void record(boolean success) {
        window.addLast(success);
        if (window.size() > windowSize) {
            window.removeFirst();
        }
        if (window.size() == windowSize) {
            long failures = window.stream().filter(s -> !s).count();
            if (failures * 100.0 / windowSize >= failureRateThreshold) {
                open();
            }
        }
    }

    private void open() {
        state = State.OPEN;
        openedAtMillis = clock.millis();
        halfOpenSuccesses = 0;
    }

    private synchronized void maybeTransitionToHalfOpen() {
        if (state == State.OPEN && clock.millis() - openedAtMillis >= waitDurationInOpen.toMillis()) {
            state = State.HALF_OPEN;
            halfOpenSuccesses = 0;
        }
    }
}
