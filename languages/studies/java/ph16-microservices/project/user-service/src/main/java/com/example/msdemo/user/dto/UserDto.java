package com.example.msdemo.user.dto;

/** 对外用户视图（不含 passwordHash/salt） */
public record UserDto(long id, String username, String role) {
}
