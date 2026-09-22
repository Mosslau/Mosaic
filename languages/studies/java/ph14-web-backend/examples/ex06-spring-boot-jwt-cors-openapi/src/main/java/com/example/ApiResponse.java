// examples/ex06-spring-boot-jwt-cors-openapi/src/main/java/com/example/ApiResponse.java —— 统一响应结构
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
package com.example;

/** 统一响应包装：code=0 成功；非 0 为业务错误码。 */
public record ApiResponse<T>(int code, String message, T data) {

    public static <T> ApiResponse<T> ok(T data) {
        return new ApiResponse<>(0, "ok", data);
    }

    public static <T> ApiResponse<T> error(int code, String message) {
        return new ApiResponse<>(code, message, null);
    }
}
