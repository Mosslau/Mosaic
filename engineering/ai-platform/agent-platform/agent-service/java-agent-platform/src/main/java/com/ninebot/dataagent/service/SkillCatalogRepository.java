package com.ninebot.dataagent.service;

import com.ninebot.dataagent.domain.ApiModels.SkillDefinition;
import com.ninebot.dataagent.domain.ApiModels.UpsertSkillRequest;
import java.util.List;

/** Skill 定义持久化端口。 */
public interface SkillCatalogRepository {
    SkillDefinition upsert(UpsertSkillRequest request);
    List<SkillDefinition> list();
    SkillDefinition get(String id);
    SkillDefinition publish(String id);
}
