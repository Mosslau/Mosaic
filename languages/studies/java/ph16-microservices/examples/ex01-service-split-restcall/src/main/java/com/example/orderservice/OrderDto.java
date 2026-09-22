package com.example.orderservice;

/** 订单（内存存储，聚焦服务间调用语义；持久化是 ph13 的内容） */
public record OrderDto(long orderId, long userId, String item) {
}
