package com.example.ordersaga;

import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;

/** 订单服务（默认端口 18216）：Saga 编排方——下单 → 扣款 → 预约物流，失败按反序补偿 */
@SpringBootApplication
public class OrderSagaApplication {

    public static void main(String[] args) {
        new SpringApplicationBuilder(OrderSagaApplication.class)
                .properties("server.port=18216")
                .run(args);
    }
}
