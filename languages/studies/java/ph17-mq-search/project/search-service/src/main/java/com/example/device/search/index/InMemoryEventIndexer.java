// 验证环境：OpenJDK 17 + Maven 3.9；单测见 InMemoryEventIndexerTest（mvn -o -Dmaven.repo.local=/tmp/m2clone -pl search-service test）
// 验证状态：未在本环境验证
package com.example.device.search.index;

import com.example.device.search.domain.DeviceEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 内存索引引擎（无中间件可跑）：eventId -> 事件的 Map + 简易关键词匹配。
 * 教学注：这里用「逐条 contains」是正排扫描（等价 MySQL LIKE），只为无中间件演示检索语义；
 * 真正的倒排索引见 examples/ex04 与主文档 4.3，真实检索用 EsEventIndexer（es 引擎）。
 */
public final class InMemoryEventIndexer implements EventIndexer {

    private static final Logger log = LoggerFactory.getLogger(InMemoryEventIndexer.class);

    private final Map<String, DeviceEvent> byId = new ConcurrentHashMap<>();

    @Override
    public void index(DeviceEvent event) {
        byId.put(event.eventId(), event); // eventId 唯一：重复写 = 覆盖（与 ES 文档 id 语义一致）
        log.info("memory index size={}", byId.size());
    }

    @Override
    public Optional<DeviceEvent> findById(String eventId) {
        return Optional.ofNullable(byId.get(eventId));
    }

    @Override
    public List<DeviceEvent> search(String q, String type, String severity) {
        String needle = q == null ? "" : q.toLowerCase(Locale.ROOT);
        return byId.values().stream()
                .filter(e -> type == null || type.equals(e.type()))
                .filter(e -> severity == null || severity.equals(e.severity()))
                .filter(e -> needle.isEmpty()
                        || e.message().toLowerCase(Locale.ROOT).contains(needle)
                        || e.type().toLowerCase(Locale.ROOT).contains(needle)
                        || e.sn().toLowerCase(Locale.ROOT).contains(needle))
                .sorted(Comparator.comparingLong(DeviceEvent::ts).reversed())
                .toList();
    }

    @Override
    public Map<String, Long> countBySeverity() {
        Map<String, Long> counts = new HashMap<>();
        byId.values().forEach(e -> counts.merge(e.severity(), 1L, Long::sum));
        return counts;
    }

    /** 供测试/调试清空 */
    void clear() {
        byId.clear();
    }
}
