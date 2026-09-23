// 验证环境：OpenJDK 17 + Maven 3.9；测试命令：mvn -o -Dmaven.repo.local=/tmp/m2clone -pl search-service test
// 验证状态：未在本环境验证
package com.example.device.search.index;

import com.example.device.search.domain.DeviceEvent;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** 内存引擎的检索语义：过滤/关键词/分组统计与 ES 引擎行为约定对齐（无需中间件，未在本环境验证） */
class InMemoryEventIndexerTest {

    private InMemoryEventIndexer indexer;

    @BeforeEach
    void setUp() {
        indexer = new InMemoryEventIndexer();
        indexer.clear();
        indexer.index(event("e1", "sn-001", 1, "alarm", "HIGH", "component low on sn-001", 3000));
        indexer.index(event("e2", "sn-002", 1, "heartbeat", "LOW", "heartbeat ok from sn-002", 2000));
        indexer.index(event("e3", "sn-003", 1, "alarm", "CRITICAL", "overheat detected", 1000));
    }

    private static DeviceEvent event(String id, String sn, long seq, String type, String severity,
                                     String message, long ts) {
        return new DeviceEvent(id, sn, seq, type, severity, message, ts);
    }

    @Test
    void indexIsIdempotentByEventId() {
        DeviceEvent dup = event("e1", "sn-001", 2, "alarm", "HIGH", "updated", 4000);
        indexer.index(dup); // 同 eventId 覆盖（与 ES 文档 id 语义一致）
        assertEquals(3, indexer.countBySeverity().values().stream().mapToLong(Long::longValue).sum(),
                "覆盖不增加文档数");
        assertEquals("updated", indexer.findById("e1").orElseThrow().message(), "覆盖后取到新内容");
    }

    @Test
    void searchFiltersByTypeAndSeverity() {
        List<DeviceEvent> alarms = indexer.search(null, "alarm", null);
        assertEquals(List.of("e1", "e3"), alarms.stream().map(DeviceEvent::eventId).toList(),
                "type=alarm 命中两条，按 ts 倒序 e1 在前");
        List<DeviceEvent> critical = indexer.search(null, "alarm", "CRITICAL");
        assertEquals(List.of("e3"), critical.stream().map(DeviceEvent::eventId).toList(),
                "type=alarm + severity=CRITICAL 只命中 e3");
    }

    @Test
    void searchKeywordIsCaseInsensitiveAcrossMessageTypeSn() {
        assertEquals(2, indexer.search("ALARM", null, null).size(), "q 命中 message/type 里的 alarm（大小写不敏感）");
        assertEquals(1, indexer.search("sn-002", null, null).size(), "q 也能命中 sn");
        assertTrue(indexer.search("nothing-matches", null, null).isEmpty(), "无命中返回空列表");
    }

    @Test
    void countBySeverityGroupsCorrectly() {
        Map<String, Long> counts = indexer.countBySeverity();
        assertEquals(1L, counts.get("HIGH"), "e1 -> HIGH");
        assertEquals(1L, counts.get("LOW"), "e2 -> LOW");
        assertEquals(1L, counts.get("CRITICAL"), "e3 -> CRITICAL");
        assertEquals(3, counts.values().stream().mapToLong(Long::longValue).sum());
    }

    @Test
    void resultsAreSortedByTsDesc() {
        assertEquals(List.of("e1", "e2", "e3"),
                indexer.search(null, null, null).stream().map(DeviceEvent::eventId).toList(),
                "无过滤全量返回按 ts 倒序");
    }
}
