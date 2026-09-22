// 验证环境：OpenJDK 17 + Maven 3.9；单测见 DeviceEventDedupTest（mvn -o -Dmaven.repo.local=/tmp/m2clone -pl search-service test）
// 验证状态：未在本环境验证
package com.example.device.search.consume;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * (sn,seq) 幂等去重：同设备同序号只放行一次，seq 回退（迟到旧数据）丢弃。
 * 原理（主文档 3.4/3.5）：Kafka at-least-once 会重复投递；同 sn 消息同分区有序，所以
 * 「seq 必须严格递增」足以同时挡住「重复」与「迟到」——比通用去重表更省，因为它借了分区的序。
 * 局限：只在单实例内存有效；多实例部署需 Redis/数据库（主文档 3.4 方案表），本骨架如实标注。
 */
public final class DeviceEventDedup {

    /** sn -> 已放行的最大 seq */
    private final Map<String, Long> lastSeqBySn = new ConcurrentHashMap<>();
    private final AtomicLong accepted = new AtomicLong();
    private final AtomicLong rejected = new AtomicLong();

    /** 返回 true = 该事件是「新的」（放行）；false = 重复或迟到（丢弃） */
    public boolean tryAccept(String sn, long seq) {
        Long prev = lastSeqBySn.putIfAbsent(sn, seq);
        if (prev == null) {
            accepted.incrementAndGet();
            return true;
        }
        boolean newSeq = seq > prev;
        if (newSeq) {
            // CAS 式推进：并发下只有更大的 seq 能赢（单分区单线程下不会并发，这里防御性处理）
            while (true) {
                long current = lastSeqBySn.get(sn);
                if (seq <= current) {
                    rejected.incrementAndGet();
                    return false;
                }
                if (lastSeqBySn.replace(sn, current, seq)) {
                    break;
                }
            }
            accepted.incrementAndGet();
            return true;
        }
        rejected.incrementAndGet();
        return false;
    }

    public long acceptedCount() {
        return accepted.get();
    }

    public long rejectedCount() {
        return rejected.get();
    }
}
