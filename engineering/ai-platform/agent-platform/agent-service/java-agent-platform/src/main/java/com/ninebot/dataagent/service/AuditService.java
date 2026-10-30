package com.ninebot.dataagent.service;

import java.util.Map;
import org.springframework.stereotype.Service;

/** 审计应用服务，统一保留运行生命周期关键事件。 */
@Service
public class AuditService {
    private final AuditPersistence persistence;
    public AuditService(AuditPersistence persistence) { this.persistence = persistence; }
    public void record(String runId, String tenantId, String eventType, Map<String, Object> payload) {
        persistence.record(runId, tenantId, eventType, payload);
    }
}
