package com.example.ex02;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.kafka.annotation.EnableKafka;

/**
 * ex02 入口：spring-kafka 注解式可靠消费 + 幂等去重（主文档 3.2/3.3/3.4）。
 * 验证环境：OpenJDK 17 + Maven 3.9 + Spring Boot 3.3.0 + spring-kafka 3.2.0（pom 见本工程）。
 * 验证命令（需本地 Kafka，docker compose 见 examples/README.md）：
 *   mvn -o -Dmaven.repo.local=/tmp/m2clone spring-boot:run -Dspring-boot.run.main-class=com.example.ex02.Ex02Application
 *   另开终端执行 ex01 的 ProducerMain（连发两遍，观察重复投递被去重表挡下）
 * 验证状态：未在本环境验证（需要 Kafka broker）。
 */
@SpringBootApplication
@EnableKafka
public class Ex02Application {

    public static void main(String[] args) {
        SpringApplication.run(Ex02Application.class, args);
    }
}
