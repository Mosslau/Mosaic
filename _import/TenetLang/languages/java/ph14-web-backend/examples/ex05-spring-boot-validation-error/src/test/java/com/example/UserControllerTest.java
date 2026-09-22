// examples/ex05-spring-boot-validation-error/src/test/java/com/example/UserControllerTest.java
// —— 参数校验 + 全局异常处理的 MockMvc 测试
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0 + JUnit Jupiter 5.10.2（本机离线 mvn -o 实测）
// 验证状态：已验证（mvn -o test，BUILD SUCCESS）
// 实测结果：Tests run: 4, Failures: 0, Errors: 0, Skipped: 0
// ---------------------------------------------------------------------------
// 教学点：@WebMvcTest 需要把 GlobalExceptionHandler 也列进来（它也是 MVC 组件），
// 否则校验异常不会被统一处理、测试看到的是 Spring 默认错误响应。
package com.example;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest({UserController.class, GlobalExceptionHandler.class})
class UserControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void validBodyCreatesUser() throws Exception {
        mockMvc.perform(post("/api/users")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\":\"Alice\",\"email\":\"alice@example.com\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.id").value(1))
                .andExpect(jsonPath("$.data.name").value("Alice"));
    }

    @Test
    void blankNameRejected() throws Exception {
        mockMvc.perform(post("/api/users")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\":\"  \",\"email\":\"alice@example.com\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(40001))
                .andExpect(jsonPath("$.data.name").value("name 不能为空"));
    }

    @Test
    void badEmailRejected() throws Exception {
        mockMvc.perform(post("/api/users")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\":\"Bob\",\"email\":\"not-an-email\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(40001))
                .andExpect(jsonPath("$.data.email").value("email 格式不正确"));
    }

    @Test
    void tooLongNameRejected() throws Exception {
        mockMvc.perform(post("/api/users")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\":\"123456789012345678901\",\"email\":\"a@b.com\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(40001))
                .andExpect(jsonPath("$.data.name").value("name 最长 20 字符"));
    }
}
