package com.example.orderservice;

/** 下游用户不存在（user-service 返回 404） */
public class UserNotFoundException extends RuntimeException {

    public UserNotFoundException(long userId) {
        super("user-service 查无用户 id=" + userId);
    }
}
