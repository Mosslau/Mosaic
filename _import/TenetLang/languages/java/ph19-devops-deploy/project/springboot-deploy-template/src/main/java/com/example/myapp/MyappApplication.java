package com.example.myapp;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * ph19 部署模板的应用入口（对应主文档 3.2：main 方法所在即 Boot 的 Start-Class）。
 * 验证状态：未在本环境验证（需 mvn + Boot 依赖；本机无 mvn）
 */
@SpringBootApplication
public class MyappApplication {

    public static void main(String[] args) {
        SpringApplication.run(MyappApplication.class, args);
    }
}
