package com.ninebot.dataagent.service;

import com.ninebot.dataagent.domain.ApiModels.AgentDefinition;
import com.ninebot.dataagent.domain.ApiModels.RunAccepted;
import com.ninebot.dataagent.domain.ApiModels.RunRequest;
import com.ninebot.dataagent.domain.ApiModels.RunView;
import java.time.Instant;
import java.util.UUID;
import org.springframework.stereotype.Service;

/**
 * AgentRun 控制面编排：生成/校验 runId、补齐 Agent Snapshot、调用 Python Runtime 并保存状态。
 *
 * <p>浏览器可以只传 agentId；Java 会从控制面目录读取已发布快照并下发给 Python，避免
 * 客户端伪造模型、工具或 Sandbox 策略。调试场景仍允许显式传 agent JSON，但生产建议关闭该路径。</p>
 */
@Service
public class RunService {
    private final RunStore store;
    private final PythonRuntimeClient runtime;
    private final AgentCatalogService agents;
    private final AuditService audit;

    public RunService(RunStore store, PythonRuntimeClient runtime, AgentCatalogService agents, AuditService audit) {
        this.store = store;
        this.runtime = runtime;
        this.agents = agents;
        this.audit = audit;
    }

    public RunAccepted submit(RunRequest request) {
        String runId = request.runId() == null || request.runId().isBlank() ? UUID.randomUUID().toString() : request.runId();
        if (store.contains(runId)) return new RunAccepted(runId, store.get(runId).status());

        AgentDefinition definition = request.agent() == null ? agents.get(request.agentId()) : null;
        if (definition != null && !"PUBLISHED".equalsIgnoreCase(definition.status())) {
            throw new IllegalArgumentException("agent is not published: " + request.agentId());
        }
        // 显式传入 Snapshot 是本地调试兼容路径；生产 API Gateway 应只允许 Java 目录快照。
        var snapshot = request.agent() == null ? definition.snapshot() : request.agent();
        Instant now = Instant.now();
        store.save(new RunView(runId, request.sessionId(), request.agentId(), "ACCEPTED", now, now, null, null));
        audit.record(runId, tenantId(request), "run_accepted", java.util.Map.of("agent_id", request.agentId()));
        RunRequest normalized = new RunRequest(runId, request.sessionId(), request.stream(), request.message(),
                request.agentId(), snapshot, request.userContext());
        try {
            RunAccepted accepted = runtime.submit(normalized);
            store.save(new RunView(runId, request.sessionId(), request.agentId(), accepted.status(), now, Instant.now(), null, null));
            audit.record(runId, tenantId(request), "runtime_accepted", java.util.Map.of("status", accepted.status()));
            return accepted;
        } catch (RuntimeException ex) {
            store.save(new RunView(runId, request.sessionId(), request.agentId(), "FAILED", now, Instant.now(), null, ex.getMessage()));
            audit.record(runId, tenantId(request), "run_submit_failed", java.util.Map.of("error", String.valueOf(ex.getMessage())));
            throw ex;
        }
    }

    public RunView get(String runId) {
        RunView local = store.get(runId);
        if (local != null) return local;
        return runtime.status(runId);
    }

    public void cancel(String runId) {
        runtime.cancel(runId);
        RunView old = store.get(runId);
        if (old != null) store.save(new RunView(old.runId(), old.sessionId(), old.agentId(), "CANCELLED",
                old.createdAt(), Instant.now(), old.result(), old.error()));
        audit.record(runId, null, "run_cancel_requested", java.util.Map.of());
    }

    private String tenantId(RunRequest request) {
        return request.userContext() == null ? null : request.userContext().tenantId();
    }
}
