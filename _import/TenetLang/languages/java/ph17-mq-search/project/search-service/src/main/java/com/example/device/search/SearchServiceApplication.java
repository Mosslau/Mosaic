package com.example.device.search;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.kafka.annotation.EnableKafka;

/**
 * search-service 入口：消费 device-events -> 幂等去重 -> 双引擎索引（memory/es）-> REST 检索。
 * 验证环境：OpenJDK 17 + Maven 3.9 + Spring Boot 3.3.0（pom 见本模块）。
 * 运行命令见 project/README.md 模式 A/B；测试命令：mvn -o -Dmaven.repo.local=/tmp/m2clone -pl search-service test。
 * 验证状态：未在本环境验证。
 */
@SpringBootApplication
@EnableKafka
public class SearchServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(SearchServiceApplication.class, args);
    }
}
