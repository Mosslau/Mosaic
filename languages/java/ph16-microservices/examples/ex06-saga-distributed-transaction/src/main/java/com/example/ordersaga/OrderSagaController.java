package com.example.ordersaga;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * Saga 编排方：PENDING →（扣款）→（预约物流）→ CONFIRMED。
 * 失败语义：业务失败（余额不足 409）→ CANCELLED，不补偿；技术/后续步骤失败且已扣款 → 补偿退款 → FAILED。
 * 补偿本身也可能失败——生产做法是把补偿投递到消息队列重试到死信（属 ph17），本示例用补偿日志留痕。
 */
@RestController
public class OrderSagaController {

    private final AccountClient accountClient;
    private final LogisticsService logisticsService;
    private final Map<String, SagaOrder> orders = new ConcurrentHashMap<>();
    private final List<String> compensationLog = new CopyOnWriteArrayList<>();

    public OrderSagaController(AccountClient accountClient, LogisticsService logisticsService) {
        this.accountClient = accountClient;
        this.logisticsService = logisticsService;
    }

    @PostMapping("/saga/orders")
    public ResponseEntity<SagaOrder> place(@RequestBody PlaceOrderRequest req) {
        SagaOrder existing = orders.putIfAbsent(req.sagaId(),
                new SagaOrder(req.sagaId(), req.accountId(), req.item(), req.amount(), "PENDING"));
        if (existing != null) {
            return ResponseEntity.ok(existing);   // Saga 幂等：同一 sagaId 重放终态，不重复执行
        }
        SagaOrder order = orders.get(req.sagaId());
        boolean debited = false;
        try {
            accountClient.debit(req.accountId(), req.amount(), req.sagaId() + ":debit");   // 步骤 1
            debited = true;
            logisticsService.reserve(req.item());                                          // 步骤 2
            order = order.withStatus("CONFIRMED");
        } catch (AccountClient.InsufficientFundsException e) {
            order = order.withStatus("CANCELLED");   // 步骤 1 业务失败：没扣成，无需补偿
        } catch (RuntimeException e) {
            if (debited) {
                // 步骤 2 失败但钱已扣 → 反向补偿（退款）。补偿动作本身也按 txId 幂等
                accountClient.refund(req.accountId(), req.amount(), req.sagaId() + ":refund");
                compensationLog.add(req.sagaId() + " refunded " + req.amount());
            }
            order = order.withStatus("FAILED");
        }
        orders.put(req.sagaId(), order);
        return ResponseEntity.ok(order);
    }

    @GetMapping("/saga/orders/{sagaId}")
    public ResponseEntity<SagaOrder> get(@PathVariable String sagaId) {
        SagaOrder order = orders.get(sagaId);
        return order == null ? ResponseEntity.notFound().build() : ResponseEntity.ok(order);
    }

    @GetMapping("/saga/compensations")
    public List<String> compensations() {
        return compensationLog;
    }
}
