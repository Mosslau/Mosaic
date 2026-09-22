package com.example.rbac;

/**
 * 统一响应壳（沿用 ph14 的 {code, message, data} 契约）：
 * code 0 成功；4xxxx 客户端错（40001 参数校验、40100 未认证、40101 登录失败、
 * 40300 无权限、40901 用户名冲突）；5xxxx 服务端错。
 */
public record ApiResponse<T>(int code, String message, T data) {

    public static <T> ApiResponse<T> ok(T data) {
        return new ApiResponse<>(0, "ok", data);
    }

    public static <T> ApiResponse<T> error(int code, String message) {
        return new ApiResponse<>(code, message, null);
    }
}
