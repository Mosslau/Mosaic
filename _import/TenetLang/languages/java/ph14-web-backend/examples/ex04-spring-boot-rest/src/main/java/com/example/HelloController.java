// examples/ex04-spring-boot-rest/src/main/java/com/example/HelloController.java —— @RestController 最小示例
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
// 验证状态：已验证（MockMvc 测试 + spring-boot:run + curl 实测，见 README）
// 实测结果（curl 直测，端口 18084）：
//   GET /api/ping → 200 {"code":0,"message":"ok","data":{"message":"pong"}}
//   GET /api/echo/Alice → 200 {"code":0,"message":"ok","data":{"echo":"Alice"}}
// ---------------------------------------------------------------------------
// 教学点：@RestController = @Controller + @ResponseBody——返回值直接序列化为 JSON 写进响应体，
// 不再需要手写 JSON 字符串（对比 ex01 的 MiniJson）。@RequestMapping 定类级前缀，
// @GetMapping/@PostMapping 定方法级路径与 HTTP 方法。
package com.example;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** 最小 REST 控制器：GET 演示。 */
@RestController
@RequestMapping("/api")
public class HelloController {

    @GetMapping("/ping")
    public ApiResponse<Object> ping() {
        return ApiResponse.ok(java.util.Map.of("message", "pong"));
    }

    @GetMapping("/echo/{name}")
    public ApiResponse<Object> echo(@PathVariable String name) {
        return ApiResponse.ok(java.util.Map.of("echo", name));
    }
}
