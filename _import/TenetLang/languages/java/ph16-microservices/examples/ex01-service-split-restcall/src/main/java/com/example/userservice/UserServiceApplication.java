package com.example.userservice;

import com.example.common.TraceIdFilter;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.annotation.Bean;

/** 用户服务：ph15 单体拆出来的第一个独立服务（默认端口 18211，命令行 --server.port 可覆盖） */
@SpringBootApplication
public class UserServiceApplication {

    public static void main(String[] args) {
        new SpringApplicationBuilder(UserServiceApplication.class)
                .properties("server.port=18211")
                .run(args);
    }

    @Bean
    TraceIdFilter traceIdFilter() {
        return new TraceIdFilter();
    }
}
