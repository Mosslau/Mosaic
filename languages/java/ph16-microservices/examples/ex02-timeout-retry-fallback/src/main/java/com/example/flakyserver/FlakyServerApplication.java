package com.example.flakyserver;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/** 故障可控的下游服务（默认端口 18213）：用于实测超时/重试/降级语义 */
@SpringBootApplication
public class FlakyServerApplication {

    public static void main(String[] args) {
        SpringApplication.run(FlakyServerApplication.class, args);
    }
}
