package com.ninebot.dataagent.service;

import java.util.Map;

/** 控制面审计事件持久化端口。 */
public interface AuditPersistence {
    void record(String runId, String tenantId, String eventType, Map<String, Object> payload);
}
