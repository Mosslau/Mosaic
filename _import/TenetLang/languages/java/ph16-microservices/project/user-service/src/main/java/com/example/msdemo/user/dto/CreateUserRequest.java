package com.example.msdemo.user.dto;

/** 创建用户请求体（仅 ADMIN 可调用） */
public record CreateUserRequest(String username, String password, String role) {
}
