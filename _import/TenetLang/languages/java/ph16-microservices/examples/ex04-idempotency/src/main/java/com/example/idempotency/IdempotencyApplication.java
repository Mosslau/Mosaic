package com.example.idempotency;

import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;

/** 幂等下单服务（默认端口 18214，main() 钉死；命令行 --server.port 可覆盖，测试用随机端口）：POST /orders 必须带 Idempotency-Key */
@SpringBootApplication
public class IdempotencyApplication {

    public static void main(String[] args) {
        new SpringApplicationBuilder(IdempotencyApplication.class)
                .properties("server.port=18214")
                .run(args);
    }
}
