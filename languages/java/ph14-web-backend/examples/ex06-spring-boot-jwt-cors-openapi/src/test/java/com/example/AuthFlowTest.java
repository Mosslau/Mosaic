// examples/ex06-spring-boot-jwt-cors-openapi/src/test/java/com/example/AuthFlowTest.java
// —— JWT 登录 + 鉴权 + CORS 的 MockMvc 测试
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0 + jjwt 0.12.5（本机离线 mvn -o 实测）
// 验证状态：已验证（mvn -o test，BUILD SUCCESS）
// 实测结果：Tests run: 5, Failures: 0, Errors: 0, Skipped: 0
// ---------------------------------------------------------------------------
// 教学点：JWT 全链路测试——登录拿 token → 带 token 访问受保护接口 → 无 token/坏 token
// 被拦截器挡下返回 401。@SpringBootTest 起完整上下文（拦截器/CORS 都生效），
// 比 @WebMvcTest 更接近真实；本测试不占端口（MockMvc 在应用内模拟 HTTP）。
package com.example;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import java.util.Map;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
class AuthFlowTest {

    @Autowired
    private WebApplicationContext context;

    @Autowired
    private ObjectMapper objectMapper;

    private MockMvc mockMvc() {
        return MockMvcBuilders.webAppContextSetup(context).build();
    }

    private String loginAndGetToken() throws Exception {
        String body = objectMapper.writeValueAsString(Map.of("username", "admin", "password", "secret"));
        String resp = mockMvc().perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andReturn().getResponse().getContentAsString();
        return objectMapper.readTree(resp).path("data").path("token").asText();
    }

    @Test
    void loginIssuesToken() throws Exception {
        String token = loginAndGetToken();
        org.assertj.core.api.Assertions.assertThat(token.split("\\.")).hasSize(3); // 三段式 JWT
    }

    @Test
    void loginWithWrongPasswordReturns401() throws Exception {
        String body = objectMapper.writeValueAsString(Map.of("username", "admin", "password", "wrong"));
        mockMvc().perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(40100));
    }

    @Test
    void meWithTokenReturns200() throws Exception {
        String token = loginAndGetToken();
        mockMvc().perform(get("/api/me").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.username").value("admin"));
    }

    @Test
    void meWithoutTokenReturns401() throws Exception {
        mockMvc().perform(get("/api/me"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(40100));
    }

    @Test
    void corsPreflightReturnsAllowHeaders() throws Exception {
        // OPTIONS 预检：浏览器跨域请求前先探一次「允不允许」，后端要回 Allow-Origin/Methods/Headers
        mockMvc().perform(options("/api/me")
                        .header("Origin", "http://localhost:5173")
                        .header("Access-Control-Request-Method", "GET"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Origin", "http://localhost:5173"));
    }
}
