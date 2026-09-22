package com.example.books;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 启动类（无 Web——本示例用 @SpringBootTest 直连仓库层验证 Spring Data 行为）。
 * @SpringBootApplication 的 @EnableAutoConfiguration 扫描到 spring-data-jpa + hsqldb 后，
 * 自动配置出 Hikari 数据源、EntityManagerFactory、JpaTransactionManager，并为 BookRepository
 * 生成实现——「starter 一个坐标 + 一个接口」的全部魔法都来自自动配置（见主文档 3.6 节）。
 */
@SpringBootApplication
public class SpringDataJpaApp {

    public static void main(String[] args) {
        SpringApplication.run(SpringDataJpaApp.class, args);
    }
}
