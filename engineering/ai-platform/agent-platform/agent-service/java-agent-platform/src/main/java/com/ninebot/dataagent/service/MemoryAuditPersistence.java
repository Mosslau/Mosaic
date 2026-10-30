package com.ninebot.dataagent.service;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Repository;

/** 开发模式审计存储；仅用于测试和本地排障。 */
@Repository
@ConditionalOnProperty(prefix = "agent.persistence", name = "mode", havingValue = "memory", matchIfMissing = true)
public class MemoryAuditPersistence implements AuditPersistence {
    private final List<Map<String, Object>> events = new CopyOnWriteArrayList<>();

    @Override
    public void record(String runId, String tenantId, String eventType, Map<String, Object> payload) {
        events.add(Map.of("run_id", runId == null ? "" : runId, "tenant_id", tenantId == null ? "" : tenantId,
                "event_type", eventType, "payload", payload == null ? Map.of() : Map.copyOf(payload),
                "created_at", Instant.now().toString()));
    }
}
