package com.ninebot.dataagent.service;

import com.ninebot.dataagent.domain.ApiModels.AgentDefinition;
import com.ninebot.dataagent.domain.ApiModels.UpsertAgentRequest;
import java.util.List;

/** Agent 定义持久化端口；控制面服务不依赖具体数据库。 */
public interface AgentCatalogRepository {
    AgentDefinition upsert(UpsertAgentRequest request);
    List<AgentDefinition> list();
    AgentDefinition get(String id);
    AgentDefinition publish(String id);
}
