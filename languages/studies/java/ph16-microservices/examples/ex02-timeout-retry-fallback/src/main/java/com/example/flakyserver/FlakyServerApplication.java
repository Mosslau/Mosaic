package com.example.flakyserver;

import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;

/** 故障可控的下游服务（默认端口 18213，main() 钉死；命令行 --server.port 可覆盖，测试用随机端口）：用于实测超时/重试/降级语义 */
@SpringBootApplication
public class FlakyServerApplication {

    public static void main(String[] args) {
        new SpringApplicationBuilder(FlakyServerApplication.class)
                .properties("server.port=18213")
                .run(args);
    }
}
