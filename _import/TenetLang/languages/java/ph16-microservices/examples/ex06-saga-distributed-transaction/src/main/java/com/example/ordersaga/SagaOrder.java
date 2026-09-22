package com.example.ordersaga;

/** Saga 订单状态机：PENDING → CONFIRMED / CANCELLED（业务失败，无补偿）/ FAILED（已补偿回滚） */
public record SagaOrder(String sagaId, long accountId, String item, long amount, String status) {

    public SagaOrder withStatus(String newStatus) {
        return new SagaOrder(sagaId, accountId, item, amount, newStatus);
    }
}
