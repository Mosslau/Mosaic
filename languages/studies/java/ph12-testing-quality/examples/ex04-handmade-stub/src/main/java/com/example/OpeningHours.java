package com.example;

import java.time.ZoneOffset;

/**
 * 营业时间判定：9:00（含）~ 18:00（不含）营业。
 * 注意：这里固定用 UTC 而非系统默认时区 —— 系统时区会随机器变化导致测试不稳定，
 * 这是「时间相关代码必须显式决定时区」的真实工程教训。
 */
public class OpeningHours {

    private final Clock clock;

    public OpeningHours(Clock clock) {
        this.clock = clock;
    }

    public boolean isOpen() {
        int hour = clock.now().atZone(ZoneOffset.UTC).getHour();
        return hour >= 9 && hour < 18;
    }
}
