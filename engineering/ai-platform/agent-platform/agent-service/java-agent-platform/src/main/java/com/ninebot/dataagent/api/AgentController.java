package com.ninebot.dataagent.api;

import com.ninebot.dataagent.domain.ApiModels.AgentDefinition;
import com.ninebot.dataagent.domain.ApiModels.PublishAgentRequest;
import com.ninebot.dataagent.domain.ApiModels.UpsertAgentRequest;
import com.ninebot.dataagent.service.AgentCatalogService;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

/** Agent 控制面 API；当前是内存实现，接口保持生产数据库实现不变。 */
@RestController
@RequestMapping("/api/agents")
public class AgentController {
    private final AgentCatalogService catalog;

    public AgentController(AgentCatalogService catalog) { this.catalog = catalog; }

    @GetMapping
    public List<AgentDefinition> list() { return catalog.list(); }

    @GetMapping("/{id}")
    public AgentDefinition get(@PathVariable String id) { return catalog.get(id); }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public AgentDefinition upsert(@Valid @RequestBody UpsertAgentRequest request) { return catalog.upsert(request); }

    @PostMapping("/{id}/publish")
    public AgentDefinition publish(@PathVariable String id, @RequestBody(required = false) PublishAgentRequest ignored) {
        return catalog.publish(id);
    }
}
