package com.ninebot.dataagent.service;

import com.ninebot.dataagent.domain.ApiModels.SkillDefinition;
import com.ninebot.dataagent.domain.ApiModels.UpsertSkillRequest;
import java.util.List;
import org.springframework.stereotype.Service;

/** Skill 控制面应用服务。 */
@Service
public class SkillCatalogService {
    private final SkillCatalogRepository repository;
    public SkillCatalogService(SkillCatalogRepository repository) { this.repository = repository; }
    public SkillDefinition upsert(UpsertSkillRequest request) { return repository.upsert(request); }
    public List<SkillDefinition> list() { return repository.list(); }
    public SkillDefinition get(String id) { return repository.get(id); }
    public SkillDefinition publish(String id) { return repository.publish(id); }
}
