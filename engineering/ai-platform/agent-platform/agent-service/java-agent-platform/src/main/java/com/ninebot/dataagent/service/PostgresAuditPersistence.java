package com.ninebot.dataagent.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Map;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/** PostgreSQL 审计事件仓储；审计写入失败会向上抛出，避免静默丢审计。 */
@Repository
@ConditionalOnProperty(prefix = "agent.persistence", name = "mode", havingValue = "postgres")
public class PostgresAuditPersistence implements AuditPersistence {
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;

    public PostgresAuditPersistence(JdbcTemplate jdbc, ObjectMapper mapper) { this.jdbc = jdbc; this.mapper = mapper; }

    @Override
    public void record(String runId, String tenantId, String eventType, Map<String, Object> payload) {
        try {
            jdbc.update("INSERT INTO audit_event(run_id, tenant_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?::jsonb, now())",
                    runId, tenantId, eventType, mapper.writeValueAsString(payload == null ? Map.of() : payload));
        } catch (JsonProcessingException ex) {
            throw new IllegalArgumentException("audit payload is not serializable", ex);
        }
    }
}
