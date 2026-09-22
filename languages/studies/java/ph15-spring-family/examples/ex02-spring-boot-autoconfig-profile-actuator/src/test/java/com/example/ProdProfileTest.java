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
 * prod profile 覆盖测试：同一套代码换 profile，文案切换 + @ConditionalOnProperty 的
 * 实验功能 Bean 被摘掉——「配置驱动装配」的最小闭环（对比 dev 默认行为）。
 * 注意：Spring Boot 配置优先级——命令行/测试属性 > 文件属性，所以这里的
 * spring.profiles.active=prod 能覆盖 application.properties 里的 dev。
 */
@SpringBootTest(properties = "spring.profiles.active=prod")
@AutoConfigureMockMvc
class ProdProfileTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void prodProfileSwitchesConfigAndConditionalBeans() throws Exception {
        mockMvc.perform(get("/api/greeting"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.profile").value("[prod]"))
                .andExpect(jsonPath("$.message").value("prod-profile-greeting"))
                .andExpect(jsonPath("$.featureEnabled").value(false))
                .andExpect(jsonPath("$.featureBeanPresent").value(false));
    }
}
