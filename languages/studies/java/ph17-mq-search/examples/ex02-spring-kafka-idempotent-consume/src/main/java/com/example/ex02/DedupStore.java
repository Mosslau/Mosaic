// 验证环境：OpenJDK 17 + Maven 3.9；构建/运行命令见本模块 pom.xml 与 examples/README.md
// 验证状态：未在本环境验证（纯逻辑类，可随 ex02 工程一起构建）
package com.example.ex02;

import java.util.concurrent.ConcurrentHashMap;

/**
 * TTL 去重表（主文档 3.4 的「去重表 / Redis SETNX」方案的内存同构版）。
 * 语义：bizKey 首次见返回 true（放行处理）；窗口内重放返回 false（跳过）；窗口过期后的重放再次放行——
 * 窗口挡不住「很晚的重复」，所以生产必须配数据库唯一约束兜底（主文档 3.4 方案表）。
 * 注意：本类只做演示，无过期清理线程（内存会随 key 数增长），生产用 Redis + TTL 或带清理的去重表。
 */
public final class DedupStore {

    private final ConcurrentHashMap<String, Long> seen = new ConcurrentHashMap<>(); // bizKey -> 过期时刻
    private final long ttlMillis;

    public DedupStore(long ttlMillis) {
        this.ttlMillis = ttlMillis;
    }

    /** 占位成功（首次见 / 已过期）返回 true，调用方应处理；窗口内重复返回 false */
    public boolean tryAcquire(String bizKey) {
        long now = System.currentTimeMillis();
        Long prev = seen.putIfAbsent(bizKey, now + ttlMillis); // 原子占位，等价 Redis SETNX
        return prev == null || prev < now;
    }
}
