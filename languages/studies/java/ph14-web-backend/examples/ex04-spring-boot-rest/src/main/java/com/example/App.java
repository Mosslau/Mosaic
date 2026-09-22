// examples/ex04-spring-boot-rest/src/main/java/com/example/App.java —— Spring Boot 启动类
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
// ---------------------------------------------------------------------------
// 教学点：@SpringBootApplication = @Configuration + @EnableAutoConfiguration +
// @ComponentScan 三合一。main 里 SpringApplication.run 启动内嵌 Tomcat——
// 前面 ex02 手写的「嵌入式 Tomcat 三件套」在这里由框架代劳。
package com.example;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class App {
    public static void main(String[] args) {
        SpringApplication.run(App.class, args);
    }
}
