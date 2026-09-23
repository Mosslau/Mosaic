package com.example.orderservice;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** 订单聚合端点：本地订单数据 + 远程用户数据 —— 微服务拆分的最小闭环 */
@RestController
public class OrderController {

    private static final Map<Long, OrderDto> ORDERS = Map.of(
            1001L, new OrderDto(1001L, 1L, "电动补能电器"),
            1002L, new OrderDto(1002L, 9L, "查无此人的订单"),
            1003L, new OrderDto(1003L, 99L, "慢用户的订单"));

    private final UserClient userClient;

    public OrderController(UserClient userClient) {
        this.userClient = userClient;
    }

    @GetMapping("/orders/{id}")
    public OrderDetail detail(@PathVariable long id) {
        OrderDto order = ORDERS.get(id);
        if (order == null) {
            throw new OrderNotFoundException(id);
        }
        UserCall call = userClient.findUser(order.userId());
        return new OrderDetail(order.orderId(), order.item(), call.user().name(), call.downstreamTraceId());
    }
}
