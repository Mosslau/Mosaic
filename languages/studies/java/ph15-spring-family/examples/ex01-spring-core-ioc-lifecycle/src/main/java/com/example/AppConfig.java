package com.example;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.annotation.Conditional;
import org.springframework.context.annotation.Configuration;

/**
 * 装配中枢：@ComponentScan 扫包内 @Component/@Service/@Repository；
 * 需要精确控制（生命周期回调、条件、命名）的 Bean 用 @Bean 显式声明。
 * 教学点：@Bean 方法是「返回对象 + 方法参数即依赖」——参数由容器按类型自动注入，
 *         与构造器注入同一套机制（方法级 DI）。
 */
@Configuration
@ComponentScan(basePackages = "com.example")
public class AppConfig {

    /**
     * 三代初始化回调叠满的观察 Bean：initMethod/destroyMethod 由这里显式点名。
     * 注意：Spring Boot 中 @Bean 的 destroyMethod 默认改为不推断（防止误杀 close()），
     * 纯 Spring Core（本示例）默认推断 public close()/shutdown() 方法。
     */
    @Bean(initMethod = "customInit", destroyMethod = "customDestroy")
    public LifecycleBean lifecycleBean() {
        return new LifecycleBean();
    }

    /** 条件装配：属性开关为 true 时才出现（实测见 LifecycleTest.testConditional） */
    @Bean
    @Conditional(OnFeatureEnabledCondition.class)
    public FeatureToggleBean featureToggleBean() {
        return new FeatureToggleBean();
    }
}
