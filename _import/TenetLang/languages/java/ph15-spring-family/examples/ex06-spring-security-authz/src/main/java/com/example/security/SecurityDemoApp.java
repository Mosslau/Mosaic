package com.example.security;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;

/**
 * 启动类：@EnableMethodSecurity 打开方法级安全（@PreAuthorize 才生效）。
 * 本示例演示 Security 的完整分层：认证（你是谁）→ URL 级授权 → 方法级授权，
 * 对比 ph14「自己写拦截器验 JWT」：Security 用一条 Filter 链 + 声明式规则接管了同一件事。
 */
@SpringBootApplication
@EnableMethodSecurity
public class SecurityDemoApp {

    public static void main(String[] args) {
        SpringApplication.run(SecurityDemoApp.class, args);
    }
}
