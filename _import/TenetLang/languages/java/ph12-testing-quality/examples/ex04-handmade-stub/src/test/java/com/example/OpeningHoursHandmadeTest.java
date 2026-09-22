package com.example;

import com.example.Clock.CountingClock;
import com.example.Clock.FixedClock;
import org.junit.jupiter.api.Test;

import java.time.Instant;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 手工替身（stub / spy）：不引入任何 mock 框架，用最朴素的接口实现控制外部依赖。
 * 对应主文档 3.3；完整工程见 examples/ex04-handmade-stub/。
 * 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + JUnit Jupiter 5.10.1（离线 mvn -o）。
 */
class OpeningHoursHandmadeTest {

    /** 构造 2026-09-01 的某小时（UTC）为固定时间点。 */
    private static Instant at(int hour) {
        return Instant.parse(String.format("2026-09-01T%02d:00:00Z", hour));
    }

    @Test
    void open_insideWorkingHours() {
        assertTrue(new OpeningHours(new FixedClock(at(10))).isOpen());
    }

    @Test
    void closed_beforeNine() {
        assertFalse(new OpeningHours(new FixedClock(at(8))).isOpen());
    }

    @Test
    void closed_afterEighteen() {
        assertFalse(new OpeningHours(new FixedClock(at(19))).isOpen());
    }

    @Test
    void boundary_exactNineIsOpen() {
        assertTrue(new OpeningHours(new FixedClock(at(9))).isOpen());
    }

    @Test
    void boundary_exactEighteenIsClosed() {
        assertFalse(new OpeningHours(new FixedClock(at(18))).isOpen());
    }

    @Test
    void now_isCalledExactlyOncePerCheck() {
        CountingClock counting = new CountingClock(at(10));
        new OpeningHours(counting).isOpen();
        assertEquals(1, counting.calls(), "每次判定应恰好调用一次 now()");
    }
}
