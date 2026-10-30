package com.ninebot.dataagent.service;

import com.ninebot.dataagent.domain.ApiModels.SkillDefinition;
import com.ninebot.dataagent.domain.ApiModels.UpsertSkillRequest;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Repository;

/** 默认开发实现：进程内保存 Skill 定义。 */
@Repository
@ConditionalOnProperty(prefix = "agent.persistence", name = "mode", havingValue = "memory", matchIfMissing = true)
public class MemorySkillCatalogRepository implements SkillCatalogRepository {
    private final Map<String, SkillDefinition> skills = new ConcurrentHashMap<>();

    @Override
    public SkillDefinition upsert(UpsertSkillRequest request) {
        SkillValidation.validate(request);
        return skills.compute(request.id(), (id, old) -> new SkillDefinition(id, request.name(), request.version(),
                request.description(), request.content(), request.bundleUrl(), request.sha256(),
                SkillValidation.tools(request.requiredTools()), request.status() == null ? "DRAFT" : request.status(), Instant.now()));
    }

    @Override
    public List<SkillDefinition> list() { return skills.values().stream().sorted(Comparator.comparing(SkillDefinition::id)).toList(); }

    @Override
    public SkillDefinition get(String id) {
        SkillDefinition value = skills.get(id);
        if (value == null) throw new IllegalArgumentException("skill not found: " + id);
        return value;
    }

    @Override
    public SkillDefinition publish(String id) {
        SkillDefinition value = get(id);
        SkillDefinition published = new SkillDefinition(value.id(), value.name(), value.version(), value.description(),
                value.content(), value.bundleUrl(), value.sha256(), value.requiredTools(), "PUBLISHED", Instant.now());
        skills.put(id, published);
        return published;
    }
}
