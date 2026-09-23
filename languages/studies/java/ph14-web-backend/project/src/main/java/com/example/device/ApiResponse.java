// project/src/main/java/com/example/device/ApiResponse.java —— 统一响应结构
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
// 验证状态：已验证
// ---------------------------------------------------------------------------
// 教学点：接口响应结构统一（roadmap 必会概念）——code/message/data 三件套贯穿
// 全部接口；业务错误码分段：0 成功 / 400xx 客户端错 / 401xx 未认证 / 409xx 冲突 / 500xx 服务端错。
package com.example.device;

/** 统一响应包装。 */
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
