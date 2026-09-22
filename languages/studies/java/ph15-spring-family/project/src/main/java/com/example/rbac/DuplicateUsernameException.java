package com.example.rbac;

/** 业务异常：用户名已被占用（全局异常处理器转 409 统一响应） */
public class DuplicateUsernameException extends RuntimeException {

    public DuplicateUsernameException(String username) {
        super("用户名已存在: " + username);
    }
}
