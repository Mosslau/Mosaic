package com.example;

/** 由开关控制的「实验性功能」Bean：demo.feature.enabled=true 才注册（由 AppConfig 的 @Bean + @Conditional 注册，故不标 @Component，避免与扫描重复定义） */
public class FeatureToggleBean {

    public String name() {
        return "experimental-feature";
    }
}
