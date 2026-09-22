package com.example;

import java.util.Optional;

/** 用户实体（record：不可变、自带 equals/hashCode/toString）。 */
public record User(long id, String name, String email) {
}
