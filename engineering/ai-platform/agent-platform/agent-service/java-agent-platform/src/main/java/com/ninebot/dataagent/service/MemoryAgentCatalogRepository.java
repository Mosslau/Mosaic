package com.ninebot.dataagent.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ninebot.dataagent.domain.ApiModels.AgentDefinition;
import com.ninebot.dataagent.domain.ApiModels.UpsertAgentRequest;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Repository;

/** 默认开发实现：进程内保存 Agent 定义。 */
@Repository
@ConditionalOnProperty(prefix = "agent.persistence", name = "mode", havingValue = "memory", matchIfMissing = true)
public class MemoryAgentCatalogRepository implements AgentCatalogRepository {
    private final Map<String, AgentDefinition> agents = new ConcurrentHashMap<>();
    private final ObjectMapper objectMapper;

    public MemoryAgentCatalogRepository(ObjectMapper objectMapper) { this.objectMapper = objectMapper; }

    @Override
    public AgentDefinition upsert(UpsertAgentRequest request) {
        var snapshot = request.snapshot() == null ? objectMapper.createObjectNode() : request.snapshot().deepCopy();
        return agents.compute(request.id(), (id, old) -> new AgentDefinition(
                id, request.name(), request.version(), request.status() == null ? "DRAFT" : request.status(),
                snapshot, Instant.now()));
    }

    @Override
    public List<AgentDefinition> list() {
        return agents.values().stream().sorted(Comparator.comparing(AgentDefinition::id)).toList();
    }

    @Override
    public AgentDefinition get(String id) {
        AgentDefinition value = agents.get(id);
        if (value == null) throw new IllegalArgumentException("agent not found: " + id);
        return value;
    }

    @Override
    public AgentDefinition publish(String id) {
        AgentDefinition value = get(id);
        AgentDefinition published = new AgentDefinition(value.id(), value.name(), value.version(), "PUBLISHED",
                value.snapshot(), Instant.now());
        agents.put(id, published);
        return published;
    }
}
