package com.example;

import org.springframework.context.annotation.Condition;
import org.springframework.context.annotation.ConditionContext;
import org.springframework.core.type.AnnotatedTypeMetadata;

/**
 * 自定义条件：System property `demo.feature.enabled=true` 时注册 Bean。
 * 这是 Spring Core 的条件装配原语——Spring Boot 的 @ConditionalOnProperty/@ConditionalOnClass
 * 就是内置了「读哪个属性 / 查哪个 class」的 Condition 实现（见 ph15 主文档 3.7 节）。
 */
public final class OnFeatureEnabledCondition implements Condition {

    public static final String PROPERTY = "demo.feature.enabled";

    @Override
    public boolean matches(ConditionContext context, AnnotatedTypeMetadata metadata) {
        return Boolean.parseBoolean(
                context.getEnvironment().getProperty(PROPERTY, "false"));
    }
}
