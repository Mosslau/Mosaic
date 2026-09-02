package com.example.accountservice;

import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;

/** 账户服务（默认端口 18215）：余额扣减/退款，按 txId 幂等 */
@SpringBootApplication
public class AccountServiceApplication {

    public static void main(String[] args) {
        new SpringApplicationBuilder(AccountServiceApplication.class)
                .properties("server.port=18215")
                .run(args);
    }
}
