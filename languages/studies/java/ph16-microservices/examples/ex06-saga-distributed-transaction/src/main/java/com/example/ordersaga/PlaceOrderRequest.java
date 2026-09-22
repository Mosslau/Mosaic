package com.example.ordersaga;

/** 下单请求：sagaId 由调用方生成（幂等键 + 全局事务号二合一） */
public record PlaceOrderRequest(String sagaId, long accountId, String item, long amount) {
}
