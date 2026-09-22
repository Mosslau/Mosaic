package com.example.msdemo.order.dto;

/**
 * 订单聚合视图：本地订单字段 + 从 user-service 远程取回的用户名。
 * degraded=true 表示用户服务没调通，userName 为降级占位文案（有损服务，HTTP 仍 200，参照 exercises/sol-02）。
 * userServiceTraceId 是 user-service 实际见到的 X-Trace-Id（链路透传的证据，参照 examples/ex01 的 OrderDetail）。
 */
public record OrderDetail(long orderId, String item, String userName, boolean degraded, String userServiceTraceId) {
}
