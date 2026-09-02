package com.example.idempotency;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import java.time.Clock;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 幂等下单端点。Idempotency-Key 头缺失 → 400；处理计数器 processCount 暴露给测试，
 * 用「业务真执行了几次」证明幂等（而不是只看返回值相同）。
 */
@RestController
public class OrderController {

    private final IdempotencyService idempotencyService;
    private final AtomicInteger processCount = new AtomicInteger();

    public OrderController() {
        // TTL 5 分钟：幂等窗口内重复提交安全，窗口外视为新请求
        this.idempotencyService = new IdempotencyService(5 * 60 * 1000L, Clock.systemUTC());
    }

    @PostMapping("/orders")
    public ResponseEntity<?> create(@RequestHeader(value = "Idempotency-Key", required = false) String key,
                                    @RequestBody CreateOrderRequest request) {
        if (key == null || key.isBlank()) {
            return ResponseEntity.badRequest()
                    .body(Map.of("code", 40001, "message", "缺少 Idempotency-Key 请求头"));
        }
        IdempotencyService.Execution<OrderResult> execution = idempotencyService.execute(key, () -> {
            processCount.incrementAndGet();   // 业务真正执行才 +1
            return new OrderResult(UUID.randomUUID().toString(), request.item(), request.quantity(), false);
        });
        OrderResult result = execution.value();
        return ResponseEntity.ok()
                .header("Idempotent-Replay", String.valueOf(execution.replayed()))
                .body(new OrderResult(result.orderId(), result.item(), result.quantity(), execution.replayed()));
    }

    @GetMapping("/admin/process-count")
    public Map<String, Integer> processCount() {
        return Map.of("processCount", processCount.get());
    }
}
