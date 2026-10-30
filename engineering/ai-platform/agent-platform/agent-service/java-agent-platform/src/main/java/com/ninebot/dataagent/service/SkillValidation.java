package com.ninebot.dataagent.service;

import com.ninebot.dataagent.domain.ApiModels.UpsertSkillRequest;
import java.util.List;

/** Skill 来源、工具依赖和版本字段的统一校验。 */
final class SkillValidation {
    private SkillValidation() {}

    static void validate(UpsertSkillRequest request) {
        boolean hasContent = request.content() != null && !request.content().isBlank();
        boolean hasBundle = request.bundleUrl() != null && !request.bundleUrl().isBlank();
        if (hasContent == hasBundle) {
            throw new IllegalArgumentException("Skill must provide exactly one of content or bundleUrl");
        }
        if (request.requiredTools() != null && request.requiredTools().stream().anyMatch(v -> v == null || v.isBlank())) {
            throw new IllegalArgumentException("Skill requiredTools cannot contain blank values");
        }
    }

    static List<String> tools(List<String> tools) { return tools == null ? List.of() : List.copyOf(tools); }
}
