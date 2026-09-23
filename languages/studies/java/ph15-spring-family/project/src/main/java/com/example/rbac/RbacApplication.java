package com.example.rbac;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;

/**
 * 权限管理系统（RBAC 起步）——ph15 阶段综合项目。
 * 技术栈 = ph15 全家桶闭环：Spring Data JPA（用户表）+ Spring Security（JWT 无状态认证 +
 * URL 级授权；@EnableMethodSecurity 已开启，方法级 @PreAuthorize 用法见 examples/ex06）+
 * Bean Validation（登录/创建参数）+ 统一响应 + 全局异常；
 * 对比 ph14 project：数据层从手写 DeviceStore 换成 JPA Repository，鉴权从 Controller
 * 拦截器验 JWT 换成 Security Filter 链原生认证。
 */
@SpringBootApplication
@EnableMethodSecurity
@ConfigurationPropertiesScan
public class RbacApplication {

    public static void main(String[] args) {
        SpringApplication.run(RbacApplication.class, args);
    }
}
