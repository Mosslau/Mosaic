package com.example.idempotency;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/** 幂等下单服务（默认端口 18214）：POST /orders 必须带 Idempotency-Key */
@SpringBootApplication
public class IdempotencyApplication {

    public static void main(String[] args) {
        SpringApplication.run(IdempotencyApplication.class, args);
    }
}
