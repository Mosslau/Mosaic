package com.example.msdemo.common.api;

/**
 * 统一响应壳（沿用 ph15 project 的 {code, message, data} 契约）：
 * code 0 成功；4xxxx 客户端错；5xxxx 服务端错。业务码语义见 {@link BizCodes}。
 */
public record ApiResponse<T>(int code, String message, T data) {

    public static <T> ApiResponse<T> ok(T data) {
        return new ApiResponse<>(0, "ok", data);
    }

    public static <T> ApiResponse<T> error(int code, String message) {
        return new ApiResponse<>(code, message, null);
    }
}
