package com.example.userservice;

/** 用户 DTO（record，不可变） */
public record UserDto(long id, String name, String city) {
}
