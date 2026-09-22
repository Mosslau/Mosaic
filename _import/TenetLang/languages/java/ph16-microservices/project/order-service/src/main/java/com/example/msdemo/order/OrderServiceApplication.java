package com.example.msdemo.order;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 订单服务入口（默认端口 18312）。
 * 职责：本地订单数据（内存表，聚焦服务拆分语义，不引数据库）+ 远程调用 user-service 聚合用户名。
 * 与 examples/ex01 同构：服务边界 = 进程边界 + 数据边界，订单数据私有，要用户名走 user-service 的 API。
 */
@SpringBootApplication
public class OrderServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(OrderServiceApplication.class, args);
    }
}
