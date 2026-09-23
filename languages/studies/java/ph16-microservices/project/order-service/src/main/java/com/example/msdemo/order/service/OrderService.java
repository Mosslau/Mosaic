package com.example.msdemo.order.service;

import com.example.msdemo.order.domain.Order;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 内存订单表（聚焦服务拆分语义，不引数据库——与 user-service 的 UserService 同一取舍）。
 * 种子订单 userId 指向 user-service 种子用户：alice id=2（18311 起真实 user-service 实测时可用）。
 * 1002 故意指向不存在的用户 id=999，用于演示「下游 404 → 订单详情 40400」的确定失败语义。
 */
@Service
public class OrderService {

    private final Map<Long, Order> orders = new ConcurrentHashMap<>();

    public OrderService() {
        orders.put(1001L, new Order(1001L, 2L, "电动充电电器"));
        orders.put(1002L, new Order(1002L, 999L, "查无此人的订单"));
        orders.put(1003L, new Order(1003L, 1L, "智能头盔"));
    }

    /** 按 id 查订单；不存在返回 null（由 Controller 翻成 40400） */
    public Order findById(long orderId) {
        return orders.get(orderId);
    }
}
