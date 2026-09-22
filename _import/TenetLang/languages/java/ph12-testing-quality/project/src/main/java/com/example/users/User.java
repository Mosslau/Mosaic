package com.example.users;

/**
 * 用户实体（record：不可变，自带 equals/hashCode/toString）。
 * id 为 0 表示「尚未分配」，由存储层落库时生成。
 */
public record User(long id, String name, String email) {
}
