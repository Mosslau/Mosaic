package com.example.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.provisioning.InMemoryUserDetailsManager;
import org.springframework.security.web.SecurityFilterChain;

/**
 * Security 配置中枢：
 * 1) SecurityFilterChain = 一条声明式的 Filter 链（认证入口、会话策略、URL 授权、异常出口）
 * 2) UserDetailsService + PasswordEncoder = 「用户从哪来、密码怎么验」
 * 3) 401/403 处理器 = 认证/授权失败时写统一 JSON（默认行为是 HTML 错误页）
 */
@Configuration
@EnableWebSecurity
public class WebSecurityConfig {

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http, ObjectMapper mapper) throws Exception {
        http
                .csrf(csrf -> csrf.disable()) // 无状态 REST：无 cookie，CSRF 防护不需要（见主文档 3.11）
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .httpBasic(Customizer.withDefaults()) // 认证方式：HTTP Basic（演示用；生产常用 JWT Filter，见 project/）
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/public/**").permitAll()
                        .requestMatchers("/api/admin/**").hasRole("ADMIN") // URL 级粗粒度授权
                        .anyRequest().authenticated())                     // 其余一律要认证
                .exceptionHandling(e -> e
                        .authenticationEntryPoint((req, res, ex) ->    // 未认证 → 401
                                JsonErrors.write(res, mapper, 401, 40100, "未认证：请携带有效凭证"))
                        .accessDeniedHandler((req, res, ex) ->         // 已认证但无权 → 403
                                JsonErrors.write(res, mapper, 403, 40300, "无权限：需要 ADMIN 角色")));
        return http.build();
    }

    /** 内存用户表（演示用）：真实项目换成数据库 UserDetailsService（见 project/ 与 exercises/sol-05） */
    @Bean
    public UserDetailsService userDetailsService(PasswordEncoder encoder) {
        var admin = User.withUsername("admin").password(encoder.encode("admin123")).roles("ADMIN").build();
        var user = User.withUsername("user").password(encoder.encode("user123")).roles("USER").build();
        return new InMemoryUserDetailsManager(admin, user);
    }

    /** BCrypt：单向哈希 + 盐，绝不存明文（对比 ph14 jjwt 的 HMAC：一个验「谁签的」，一个存「谁的密码」） */
    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}
