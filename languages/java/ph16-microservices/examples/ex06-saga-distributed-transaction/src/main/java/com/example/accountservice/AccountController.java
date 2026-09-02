package com.example.accountservice;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 账户端点。每个写操作带 txId 且幂等（processedTx 去重）——Saga 重试/补偿重放不产生二次效果。
 * 为聚焦 Saga 语义，余额用内存 Map（真实系统是各服务自己的数据库 + 唯一约束）。
 */
@RestController
public class AccountController {

    private final Map<Long, AtomicLong> balances = new ConcurrentHashMap<>(Map.of(
            1L, new AtomicLong(10_000L),
            2L, new AtomicLong(50L)));          // 账户 2 余额不足，用于测「步骤失败不补偿」
    private final Set<String> processedTx = ConcurrentHashMap.newKeySet();

    @GetMapping("/accounts/{id}")
    public Map<String, Long> balance(@PathVariable long id) {
        AtomicLong balance = balances.get(id);
        if (balance == null) {
            return Map.of("balance", -1L);
        }
        return Map.of("balance", balance.get());
    }

    /** 扣减：幂等；余额不足 → 409（业务失败，Saga 不应补偿，直接取消） */
    @PostMapping("/accounts/{id}/debit")
    public ResponseEntity<Map<String, Object>> debit(@PathVariable long id, @RequestBody AmountRequest req) {
        AtomicLong balance = balances.get(id);
        if (balance == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "account not found"));
        }
        if (!processedTx.add(req.txId())) {
            return ResponseEntity.ok(Map.of("txId", req.txId(), "duplicated", true, "balance", balance.get()));
        }
        long remaining = balance.addAndGet(-req.amount());
        if (remaining < 0) {
            balance.addAndGet(req.amount());   // 扣不动就退回，保持原子
            return ResponseEntity.status(HttpStatus.CONFLICT)
                    .body(Map.of("error", "insufficient funds", "balance", balance.get()));
        }
        return ResponseEntity.ok(Map.of("txId", req.txId(), "debited", req.amount(), "balance", remaining));
    }

    /** 退款（Saga 补偿动作）：同样按 txId 幂等，补偿重放不多退 */
    @PostMapping("/accounts/{id}/refund")
    public ResponseEntity<Map<String, Object>> refund(@PathVariable long id, @RequestBody AmountRequest req) {
        AtomicLong balance = balances.get(id);
        if (balance == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "account not found"));
        }
        if (!processedTx.add(req.txId())) {
            return ResponseEntity.ok(Map.of("txId", req.txId(), "duplicated", true, "balance", balance.get()));
        }
        long remaining = balance.addAndGet(req.amount());
        return ResponseEntity.ok(Map.of("txId", req.txId(), "refunded", req.amount(), "balance", remaining));
    }
}
