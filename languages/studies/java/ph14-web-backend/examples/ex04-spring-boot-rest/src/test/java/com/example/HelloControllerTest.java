// examples/ex04-spring-boot-rest/src/test/java/com/example/HelloControllerTest.java —— MockMvc 测试
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0 + JUnit Jupiter 5.10.2（本机离线 mvn -o 实测）
// 验证状态：已验证（mvn -o test，BUILD SUCCESS）
// 实测结果：Tests run: 3, Failures: 0, Errors: 0, Skipped: 0
// ---------------------------------------------------------------------------
// 教学点：@WebMvcTest 只切 Controller 层（不启动完整应用），MockMvc 模拟 HTTP 请求——
// 不占端口、不启 Tomcat，是 Controller 层测试的标准姿势（ph12 测试阶段的框架测试落地）。
// jsonPath 用类似 JSONPath 的语法断言响应体（ph12 的 AssertJ 风格断言在 REST 测试里的对应物）。
package com.example;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(HelloController.class)
class HelloControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void pingReturnsUnifiedResponse() throws Exception {
        mockMvc.perform(get("/api/ping"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.message").value("ok"))
                .andExpect(jsonPath("$.data.message").value("pong"));
    }

    @Test
    void echoReturnsPathVariable() throws Exception {
        mockMvc.perform(get("/api/echo/Alice"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.echo").value("Alice"));
    }

    @Test
    void echoWithChineseNameWorks() throws Exception {
        // UTF-8 路径参数：MockMvc 直接传中文（真实 HTTP 里客户端会做百分号编码，
        // Tomcat 自动解码；本测试聚焦「中文经过 @PathVariable 不被截断」）
        mockMvc.perform(get("/api/echo/{name}", "张三"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.echo").value("张三"));
    }
}
