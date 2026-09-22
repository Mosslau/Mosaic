package com.example;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 类型安全配置：@ConfigurationProperties 把 application-*.properties 的 app.greeting.*
 * 绑定进强类型对象——IDE 补全、编译期字段检查，代替散落的 @Value("${...}")。
 * （record 不可变 + 构造器绑定是 Spring Boot 3 推荐的写法）
 */
@ConfigurationProperties(prefix = "app.greeting")
public record GreetingProperties(
        String message,
        boolean featureEnabled
) {
}
