package com.example.idempotency;

import java.time.Clock;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Supplier;

/**
 * 幂等键存储的最小同构实现（生产等价物：Redis SET NX PX / 数据库唯一约束，见主文档 3.5）。
 * 语义：同一 key 只执行一次业务逻辑，后续相同 key 重放首个结果（replayed=true）；
 * 并发撞 key 时，后来者等待首个请求完成拿同一结果；业务失败不缓存（允许客户端重试）；
 * 条目带 TTL，过期后可再次处理（幂等窗口 ≠ 永久）。
 */
public class IdempotencyService {

    /** 执行结果：值 + 是否为重放 */
    public record Execution<T>(T value, boolean replayed) {
    }

    private record Entry(Object value, long expiresAtMillis) {
    }

    private final ConcurrentHashMap<String, CompletableFuture<Entry>> store = new ConcurrentHashMap<>();
    private final long ttlMillis;
    private final Clock clock;

    public IdempotencyService(long ttlMillis, Clock clock) {
        this.ttlMillis = ttlMillis;
        this.clock = clock;
    }

    @SuppressWarnings("unchecked")
    public <T> Execution<T> execute(String key, Supplier<T> business) {
        while (true) {
            CompletableFuture<Entry> first = new CompletableFuture<>();
            CompletableFuture<Entry> existing = store.putIfAbsent(key, first);
            if (existing != null) {
                Entry entry = existing.join();   // 首个请求未完成时在此等待，完成后拿同一结果
                if (entry.expiresAtMillis() < clock.millis()) {
                    store.remove(key, existing); // 已过期：移除后重试占位
                    continue;
                }
                return new Execution<>((T) entry.value(), true);   // 重放首个结果，不再执行 business
            }
            try {
                T value = business.get();
                first.complete(new Entry(value, clock.millis() + ttlMillis));
                return new Execution<>(value, false);
            } catch (RuntimeException e) {
                store.remove(key, first);        // 失败不缓存：客户端可安全重试
                first.completeExceptionally(e);
                throw e;
            }
        }
    }

    public int size() {
        return store.size();
    }
}
