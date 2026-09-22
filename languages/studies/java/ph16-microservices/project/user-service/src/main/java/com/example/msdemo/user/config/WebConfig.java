package com.example.msdemo.user.config;

import com.example.msdemo.common.jwt.JwtService;
import com.example.msdemo.common.trace.TraceIdFilter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** 装配：JwtService（secret 走配置）+ TraceIdFilter（order=1，最先进入） */
@Configuration
public class WebConfig {

    @Bean
    JwtService jwtService(@Value("${jwt.secret}") String secret,
                          @Value("${jwt.ttl-hours:2}") long ttlHours) {
        return new JwtService(secret, ttlHours);
    }

    @Bean
    FilterRegistrationBean<TraceIdFilter> traceIdFilter() {
        FilterRegistrationBean<TraceIdFilter> registration = new FilterRegistrationBean<>(new TraceIdFilter());
        registration.setOrder(1);
        registration.addUrlPatterns("/*");
        return registration;
    }
}
