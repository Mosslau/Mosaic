package com.example;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * ex02 测试：默认 profile（dev）行为 + actuator 端点。
 * 验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone test
 */
@SpringBootTest
@AutoConfigureMockMvc
class AutoconfigProfileActuatorTest {

    @Autowired
    private MockMvc mockMvc;

    /** 默认激活 dev（application.properties 里 spring.profiles.active=dev）：文案来自 dev 文件，条件 Bean 在位 */
    @Test
    void devProfileIsActiveByDefault() throws Exception {
        mockMvc.perform(get("/api/greeting"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.profile").value("[dev]"))
                .andExpect(jsonPath("$.message").value("dev-profile-greeting"))
                .andExpect(jsonPath("$.featureEnabled").value(true))
                .andExpect(jsonPath("$.featureBeanPresent").value(true));
    }

    /** actuator 自动配置的可观察证据：引了 starter-actuator，/actuator/* 端点开箱即用 */
    @Test
    void actuatorEndpointsAppearByAutoConfiguration() throws Exception {
        mockMvc.perform(get("/actuator/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("UP"));
        mockMvc.perform(get("/actuator/info"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.app.name").value("ph15-ex02-profile-actuator"))
                .andExpect(jsonPath("$.app.env").value("dev"));
    }
}
