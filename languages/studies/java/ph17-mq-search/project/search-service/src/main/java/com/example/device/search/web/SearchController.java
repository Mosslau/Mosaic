// 验证环境：OpenJDK 17 + Maven 3.9 + Spring Boot 3.3.0；构建/运行命令见 search-service/pom.xml 与 project/README.md
// 验证状态：未在本环境验证
package com.example.device.search.web;

import com.example.device.search.domain.DeviceEvent;
import com.example.device.search.index.EventIndexer;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 检索与注入端点（索引引擎由 app.search.engine 决定，controller 不感知底层——EventIndexer 抽象）：
 *  - POST /api/events         直接注入事件（无 Kafka 环境造数，模式 A）
 *  - GET  /api/events/{id}    按 eventId 精确查
 *  - GET  /api/events/search  组合检索：q 关键词 + type/severity 过滤（可空），按 ts 倒序
 *  - GET  /api/events/count   按 severity 分组统计
 */
@RestController
@RequestMapping("/api/events")
public class SearchController {

    private final EventIndexer indexer;
    private final AtomicLong seqGen = new AtomicLong(1);

    public SearchController(EventIndexer indexer) {
        this.indexer = indexer;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public DeviceEvent inject(@RequestBody DeviceEventRequest request) {
        String sn = request.sn();
        if (sn == null || sn.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "sn is required");
        }
        DeviceEvent event = new DeviceEvent(
                UUID.randomUUID().toString(),
                sn,
                seqGen.incrementAndGet(),
                request.type() == null ? "heartbeat" : request.type(),
                request.severity() == null ? "LOW" : request.severity(),
                request.message() == null ? "no message" : request.message(),
                System.currentTimeMillis());
        indexer.index(event);
        return event;
    }

    @GetMapping("/{eventId}")
    public DeviceEvent getById(@PathVariable String eventId) {
        return indexer.findById(eventId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND,
                        "event not found: " + eventId));
    }

    @GetMapping("/search")
    public List<DeviceEvent> search(@RequestParam(required = false) String q,
                                    @RequestParam(required = false) String type,
                                    @RequestParam(required = false) String severity) {
        return indexer.search(q, type, severity);
    }

    @GetMapping("/count")
    public Map<String, Long> countBySeverity() {
        return indexer.countBySeverity();
    }
}
