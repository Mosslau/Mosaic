package com.example;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * 条件装配的 Boot 版：@ConditionalOnProperty 是 Spring Core @Conditional（ex01）的
 * 「读属性」内置实现——app.greeting.feature-enabled=true 才注册 ExtraFeatureBean。
 * 与 profile 组合：dev 开、prod 关（见 application-dev/prod.properties），
 * 同一个二进制、不同环境装配不同的 Bean——「配置驱动装配」的最小演示。
 */
@Configuration
public class FeatureConfig {

    @Bean
    @ConditionalOnProperty(name = "app.greeting.feature-enabled", havingValue = "true")
    public ExtraFeatureBean extraFeatureBean() {
        return new ExtraFeatureBean();
    }

    public record ExtraFeatureBean() {
    }
}
