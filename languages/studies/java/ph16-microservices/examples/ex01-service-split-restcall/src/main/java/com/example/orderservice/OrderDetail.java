package com.example.orderservice;

/** 订单聚合视图：订单字段 + 从 user-service 远程取回的用户名 + 下游实际见到的 traceId（验证透传用） */
public record OrderDetail(long orderId, String item, String userName, String userServiceTraceId) {
}
