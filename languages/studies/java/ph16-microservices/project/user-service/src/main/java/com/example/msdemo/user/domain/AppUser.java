package com.example.msdemo.user.domain;

/** 用户实体（内存存储；passwordHash/salt 永不外泄——对外只暴露 UserDto） */
public record AppUser(long id, String username, String passwordHash, String salt, String role) {
}
