package com.example;

import java.time.Instant;
import java.time.ZoneOffset;

/**
 * 时间源接口：把「当前时间」抽象为可注入依赖。
 * 真实实现是系统时钟；测试用手工 stub 固定时间 —— 让「时间相关」的逻辑可测。
 */
public interface Clock {

    Instant now();

    /** 固定返回给定时间的 stub，供测试使用（手工替身，无任何框架）。 */
    final class FixedClock implements Clock {
        private final Instant fixed;

        public FixedClock(Instant fixed) {
            this.fixed = fixed;
        }

        @Override
        public Instant now() {
            return fixed;
        }
    }

    /** 记录 now() 调用次数的 spy，供测试验证交互（手工替代 Mockito 的 verify）。 */
    final class CountingClock implements Clock {
        private final Instant now;
        private int calls;

        public CountingClock(Instant now) {
            this.now = now;
        }

        @Override
        public Instant now() {
            calls++;
            return now;
        }

        public int calls() {
            return calls;
        }
    }
}
