package com.example;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * 拦截器注册中枢：addInterceptor 的先后顺序 = preHandle 的执行顺序。
 * 拦截器实例在这里 new 出来（不进容器），需要依赖就在构造器里由 Spring 注入（本示例无依赖）。
 */
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(new FirstInterceptor())
                .addPathPatterns("/api/**");   // 只拦 /api/**
        registry.addInterceptor(new SecondInterceptor())
                .addPathPatterns("/api/**");
    }
}
