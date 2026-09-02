package com.example;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/** 启动类：演示 HandlerInterceptor 拦截器链与 Filter 的定位区别（主文档 3.6 节） */
@SpringBootApplication
public class MvcInterceptorApp {

    public static void main(String[] args) {
        SpringApplication.run(MvcInterceptorApp.class, args);
    }
}
