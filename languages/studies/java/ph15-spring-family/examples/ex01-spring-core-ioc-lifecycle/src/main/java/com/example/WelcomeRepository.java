package com.example;

import org.springframework.stereotype.Repository;

import java.util.List;

/** 模拟数据访问层（ph13 真实落库版见 examples/ex05-spring-data-jpa） */
@Repository
public class WelcomeRepository {

    public List<String> greetings() {
        return List.of("你好", "Hello", "こんにちは");
    }
}
