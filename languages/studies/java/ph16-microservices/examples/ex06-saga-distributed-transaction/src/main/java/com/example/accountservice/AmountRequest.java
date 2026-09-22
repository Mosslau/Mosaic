package com.example.accountservice;

/** 扣减/退款请求：txId 是 Saga 的全局事务号，账户服务按它做幂等 */
public record AmountRequest(long amount, String txId) {
}
