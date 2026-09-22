package com.example.orderservice;

/** 订单不存在（本地 404，与下游 404 的 UserNotFoundException 区分） */
public class OrderNotFoundException extends RuntimeException {

    public OrderNotFoundException(long orderId) {
        super("订单不存在 id=" + orderId);
    }
}
