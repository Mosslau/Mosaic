package com.ninebot.dataagent.api;

import com.ninebot.dataagent.domain.ApiModels.PublishSkillRequest;
import com.ninebot.dataagent.domain.ApiModels.SkillDefinition;
import com.ninebot.dataagent.domain.ApiModels.UpsertSkillRequest;
import com.ninebot.dataagent.service.SkillCatalogService;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

/** Skill 管理 API；发布后的定义可作为 Agent Snapshot 的 Skill 引用。 */
@RestController
@RequestMapping("/api/skills")
public class SkillController {
    private final SkillCatalogService catalog;
    public SkillController(SkillCatalogService catalog) { this.catalog = catalog; }

    @GetMapping
    public List<SkillDefinition> list() { return catalog.list(); }
    @GetMapping("/{id}")
    public SkillDefinition get(@PathVariable String id) { return catalog.get(id); }
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public SkillDefinition upsert(@Valid @RequestBody UpsertSkillRequest request) { return catalog.upsert(request); }
    @PostMapping("/{id}/publish")
    public SkillDefinition publish(@PathVariable String id, @RequestBody(required = false) PublishSkillRequest ignored) {
        return catalog.publish(id);
    }
}
