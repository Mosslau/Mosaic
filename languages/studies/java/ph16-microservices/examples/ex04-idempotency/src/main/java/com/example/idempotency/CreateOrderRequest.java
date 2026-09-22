package com.example.idempotency;

/** 下单请求 */
public record CreateOrderRequest(String item, int quantity) {
}
