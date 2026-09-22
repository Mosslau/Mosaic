package com.example;

import org.springframework.stereotype.Service;

/**
 * 构造器注入演示（Spring 官方推荐、本仓库 Java 规范要求的注入方式）：
 * final 字段 + 唯一构造器，容器按参数类型自动装配——测试友好、依赖一目了然。
 */
@Service
public class WelcomeService {

    private final WelcomeRepository repository;

    public WelcomeService(WelcomeRepository repository) {
        this.repository = repository;
    }

    public int greetingCount() {
        return repository.greetings().size();
    }

    public String firstGreeting() {
        return repository.greetings().get(0);
    }
}
