package com.example;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

/**
 * 启动类：@SpringBootApplication = @Configuration + @EnableAutoConfiguration + @ComponentScan
 * （三个注解合一，ph15 主文档 3.6 节逐层拆解）。@ConfigurationPropertiesScan 自动注册
 * 所有 @ConfigurationProperties 类为 Bean——类型安全配置读取的入口。
 */
@SpringBootApplication
@ConfigurationPropertiesScan
public class AutoconfigProfileActuatorApp {

    public static void main(String[] args) {
        SpringApplication.run(AutoconfigProfileActuatorApp.class, args);
    }
}
