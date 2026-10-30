package com.ninebot.dataagent.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

/** Skill 控制面最小契约测试。 */
@SpringBootTest(properties = {
        "agent.persistence.mode=memory",
        "agent.gateway.internal-token=test-token"
})
@AutoConfigureMockMvc
class SkillControllerTest {
    @Autowired MockMvc mvc;

    @Test
    void createsListsAndPublishesInlineSkill() throws Exception {
        mvc.perform(post("/api/skills")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"id\":\"metadata-analysis\",\"name\":\"元数据分析\",\"version\":\"1.0.0\",\"content\":\"# Skill\",\"requiredTools\":[\"metadata_search\"]}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.status").value("DRAFT"));

        mvc.perform(post("/api/skills/metadata-analysis/publish"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("PUBLISHED"));

        mvc.perform(get("/api/skills/metadata-analysis"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.requiredTools[0]").value("metadata_search"));
    }

    @Test
    void rejectsSkillWithTwoSources() throws Exception {
        mvc.perform(post("/api/skills")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"id\":\"bad\",\"name\":\"bad\",\"version\":\"1\",\"content\":\"# Skill\",\"bundleUrl\":\"s3://bucket/skill.tgz\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_REQUEST"));
    }
}
