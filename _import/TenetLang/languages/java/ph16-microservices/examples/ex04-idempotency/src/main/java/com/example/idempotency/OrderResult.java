package com.example.idempotency;

/** 下单结果（replayed=true 表示这是幂等重放，业务没再执行） */
public record OrderResult(String orderId, String item, int quantity, boolean replayed) {
}
