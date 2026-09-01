// project/src/test/java/com/example/vehicle/VehicleApiTest.java —— REST 层集成测试（MockMvc + 完整上下文）
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0 + JUnit Jupiter 5.10.2（本机离线 mvn -o 实测）
// 验证状态：已验证（mvn -o test，BUILD SUCCESS）
// 实测结果：Tests run: 7, Failures: 0, Errors: 0, Skipped: 0
// ---------------------------------------------------------------------------
// 教学点：@SpringBootTest + MockMvc 起完整上下文（Controller/Service/Store/拦截器/全局异常
// 全部生效），模拟真实 HTTP 语义而不占端口。覆盖：登录发 token → 带 token 上报 → 查状态/
// 历史；无 token 上报 401；校验失败 400（VIN 非法 / 电量越界）；未知车辆 404——正常路径与错误路径同样覆盖。
package com.example.vehicle;

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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
class VehicleApiTest {

    @Autowired
    private WebApplicationContext context;

    @Autowired
    private ObjectMapper objectMapper;

    private MockMvc mockMvc() {
        return MockMvcBuilders.webAppContextSetup(context).build();
    }

    private String loginToken() throws Exception {
        String body = objectMapper.writeValueAsString(Map.of("username", "demo", "password", "demo123"));
        String resp = mockMvc().perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        return objectMapper.readTree(resp).path("data").path("token").asText();
    }

    private String validReportBody() throws Exception {
        return objectMapper.writeValueAsString(Map.of(
                "vin", "LSVAB4BR0DA123456",
                "lat", 31.23, "lng", 121.47,
                "speedKph", 60, "batteryPct", 88));
    }

    @Test
    void loginIssuesToken() throws Exception {
        org.assertj.core.api.Assertions.assertThat(loginToken().split("\\.")).hasSize(3);
    }

    @Test
    void reportRequiresToken() throws Exception {
        mockMvc().perform(post("/api/vehicles/report")
                        .contentType(MediaType.APPLICATION_JSON).content(validReportBody()))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(40101));
    }

    @Test
    void reportAndQueryFlow() throws Exception {
        String token = loginToken();
        // 上报
        mockMvc().perform(post("/api/vehicles/report")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON).content(validReportBody()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.vin").value("LSVAB4BR0DA123456"))
                .andExpect(jsonPath("$.data.speedKph").value(60));
        // 最新状态
        mockMvc().perform(get("/api/vehicles/LSVAB4BR0DA123456/status")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.batteryPct").value(88));
        // 历史
        mockMvc().perform(get("/api/vehicles/LSVAB4BR0DA123456/reports")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").isArray());
    }

    @Test
    void invalidVinRejectedByValidation() throws Exception {
        String token = loginToken();
        String bad = objectMapper.writeValueAsString(Map.of(
                "vin", "SHORT", "lat", 31.23, "lng", 121.47, "speedKph", 60, "batteryPct", 88));
        mockMvc().perform(post("/api/vehicles/report")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON).content(bad))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(40000));
    }

    @Test
    void outOfRangeBatteryRejectedByValidation() throws Exception {
        // batteryPct=150 先被 Controller 的 @Max(100) 声明式校验拦下 → 40000（输入形状层）；
        // Service 里的 40004 业务规则兜底由 VehicleServiceTest 单元测试覆盖（两层各司其职）
        String token = loginToken();
        String bad = objectMapper.writeValueAsString(Map.of(
                "vin", "LSVAB4BR0DA123456", "lat", 31.23, "lng", 121.47, "speedKph", 60, "batteryPct", 150));
        mockMvc().perform(post("/api/vehicles/report")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON).content(bad))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(40000));
    }

    @Test
    void unknownVehicleStatus404() throws Exception {
        String token = loginToken();
        mockMvc().perform(get("/api/vehicles/LSVAB4BR0DA999999/status")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value(40401));
    }

    @Test
    void wrongPasswordRejected() throws Exception {
        String body = objectMapper.writeValueAsString(Map.of("username", "demo", "password", "wrong"));
        mockMvc().perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(40100));
    }
}
