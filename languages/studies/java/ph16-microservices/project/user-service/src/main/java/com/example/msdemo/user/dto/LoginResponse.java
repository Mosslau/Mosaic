package com.example.msdemo.user.dto;

/** 登录响应：token + 身份回显 */
public record LoginResponse(String token, String username, String role) {
}
