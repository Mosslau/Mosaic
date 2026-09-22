// examples/ex05-spring-boot-validation-error/src/main/java/com/example/ApiResponse.java —— 统一响应结构
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
// ---------------------------------------------------------------------------
// 教学点：错误路径也走同一个壳——code 是业务错误码（0=成功，4xxxx=客户端错，5xxxx=服务端错），
// HTTP 状态码表达「传输层语义」（400/404/500），业务错误码表达「业务语义」，两者分工。
package com.example;

/** 统一响应包装：code=0 成功；非 0 为业务错误码，message 给人看，data 给程序用。 */
public record ApiResponse<T>(int code, String message, T data) {

    public static <T> ApiResponse<T> ok(T data) {
        return new ApiResponse<>(0, "ok", data);
    }

    public static <T> ApiResponse<T> error(int code, String message) {
        return new ApiResponse<>(code, message, null);
    }

    public static <T> ApiResponse<T> error(int code, String message, T data) {
        return new ApiResponse<>(code, message, data);
    }
}
