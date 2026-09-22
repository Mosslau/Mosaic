// examples/ex04-spring-boot-rest/src/main/java/com/example/ApiResponse.java —— 统一响应结构
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
// ---------------------------------------------------------------------------
// 教学点：roadmap 必会概念「接口响应结构要统一」——code/message/data 三件套。
// 前端只要解析这一个形状，成功失败都走同构；业务错误码（40001 等）见 ex05。
// record 是 Java 16+ 的不可变数据载体（ph02 OOP 阶段讲过），Spring 能直接序列化成 JSON。
package com.example;

/** 统一响应包装：所有接口成功路径返回 code=0, message="ok"，数据放 data。 */
public record ApiResponse<T>(int code, String message, T data) {

    public static <T> ApiResponse<T> ok(T data) {
        return new ApiResponse<>(0, "ok", data);
    }
}
