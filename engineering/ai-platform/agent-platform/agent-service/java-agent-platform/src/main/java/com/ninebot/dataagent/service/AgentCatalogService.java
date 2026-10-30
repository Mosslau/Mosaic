package com.ninebot.dataagent.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.ninebot.dataagent.domain.ApiModels.AgentDefinition;
import com.ninebot.dataagent.domain.ApiModels.SkillDefinition;
import com.ninebot.dataagent.domain.ApiModels.UpsertAgentRequest;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * Agent 控制面应用服务。
 *
 * <p>除保存 Agent 基本信息外，还负责把快照中的 {@code skill_ids} 编译成 Python Runtime
 * 可直接消费的不可变 SkillSnapshot。这样浏览器不需要携带 Skill 内容，Java 仍然是唯一的
 * Skill 权限和版本控制入口。</p>
 */
@Service
public class AgentCatalogService {
    private final AgentCatalogRepository repository;
    private final SkillCatalogService skills;
    private final ObjectMapper objectMapper;

    public AgentCatalogService(AgentCatalogRepository repository, SkillCatalogService skills, ObjectMapper objectMapper) {
        this.repository = repository;
        this.skills = skills;
        this.objectMapper = objectMapper;
    }

    public AgentDefinition upsert(UpsertAgentRequest request) {
        return repository.upsert(new UpsertAgentRequest(request.id(), request.name(), request.version(), request.status(),
                compileSkills(request.snapshot())));
    }

    public List<AgentDefinition> list() { return repository.list(); }
    public AgentDefinition get(String id) { return repository.get(id); }
    public AgentDefinition publish(String id) { return repository.publish(id); }

    private JsonNode compileSkills(JsonNode snapshot) {
        if (snapshot == null || !snapshot.isObject()) return snapshot;
        ObjectNode result = snapshot.deepCopy();
        JsonNode skillIds = result.get("skill_ids");
        if (skillIds == null || !skillIds.isArray()) return result;

        ArrayNode compiled = objectMapper.createArrayNode();
        for (JsonNode idNode : skillIds) {
            String id = idNode.asText();
            if (id.isBlank()) throw new IllegalArgumentException("agent snapshot contains blank skill id");
            SkillDefinition skill = skills.get(id);
            if (!"PUBLISHED".equalsIgnoreCase(skill.status())) {
                throw new IllegalArgumentException("skill is not published: " + id);
            }
            ObjectNode item = objectMapper.createObjectNode();
            item.put("id", skill.id());
            item.put("version", skill.version());
            if (skill.bundleUrl() != null) item.put("bundle_url", skill.bundleUrl());
            if (skill.content() != null) item.put("content", skill.content());
            if (skill.sha256() != null) item.put("sha256", skill.sha256());
            item.set("required_tools", objectMapper.valueToTree(skill.requiredTools()));
            compiled.add(item);
        }
        result.set("skills", compiled);
        result.remove("skill_ids");
        return result;
    }
}
