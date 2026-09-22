// exercises/sol-01-async-order-process.java —— 练习 1 参考实现：异步订单处理（roadmap ph17 练习：异步订单处理）
// 验证环境：OpenJDK 17 + Maven 3.9 + Spring Boot 3.3.0 + spring-kafka 3.2.0（pom 复制 examples/ex02 的）
// 验证状态：未在本环境验证。纯 JUnit 部分（OrderStoreTest/DedupStore 单测）理论上 `mvn -o -Dmaven.repo.local=/tmp/m2clone test`
//   可离线跑（pom 需追加 test-scope spring-boot-starter-test）；Kafka 消费链路需先 `docker compose up -d kafka`
//   （examples/docker-compose.yml），用 examples/ex01 的 ProducerMain 连发两遍同 key 消息观察幂等，未在本环境实测。
// 教学点：消费端「先处理再提交」= at-least-once（主文档 3.3）；重复不可避免 -> 幂等设计在消费端（3.4）；
//   双层幂等：TTL 去重表挡窗口内重复（快），业务唯一键兜底（内存 putIfAbsent = 数据库唯一约束的最小同构）。

// =============================================================================
// src/main/java/com/example/order/OrderEvent.java
// =============================================================================

package com.example.order;

/** 订单创建事件（与 examples/ex01 ProducerMain 发的 JSON 对应） */
public record OrderEvent(String orderId, String userId, int amount) {
}

// =============================================================================
// src/main/java/com/example/order/DedupStore.java
// =============================================================================

package com.example.order;

import java.util.concurrent.ConcurrentHashMap;

/**
 * TTL 去重表：bizKey 首次见 / 已过期 -> true（放行）；窗口内重复 -> false。
 * 只挡「近重复」：很晚的重放会放行，交给 OrderStore 的唯一键兜底。
 * 生产实现：Redis SETNX + TTL，或数据库唯一约束（两者配合，见主文档 3.4 方案表）。
 */
public final class DedupStore {

    private final ConcurrentHashMap<String, Long> seen = new ConcurrentHashMap<>();
    private final long ttlMillis;

    public DedupStore(long ttlMillis) {
        this.ttlMillis = ttlMillis;
    }

    public boolean tryAcquire(String bizKey) {
        long now = System.currentTimeMillis();
        Long prev = seen.putIfAbsent(bizKey, now + ttlMillis);
        return prev == null || prev < now;
    }
}

// =============================================================================
// src/main/java/com/example/order/OrderStore.java
// =============================================================================

package com.example.order;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 订单存储（内存版）：orderId 唯一键 + 建单计数。
 * putIfAbsent 返回 null 说明首次建单 —— 内存版「唯一约束」，生产换成数据库唯一索引（3.4 的最终防线）。
 */
public final class OrderStore {

    private final Map<String, String> orders = new ConcurrentHashMap<>(); // orderId -> userId
    private final AtomicInteger created = new AtomicInteger();

    /** 首次建单返回 true；orderId 已存在返回 false（重复投递不会二次建单） */
    public boolean tryCreate(OrderEvent event) {
        boolean first = orders.putIfAbsent(event.orderId(), event.userId()) == null;
        if (first) {
            created.incrementAndGet();
        }
        return first;
    }

    public int createdCount() {
        return created.get();
    }
}

// =============================================================================
// src/main/java/com/example/order/OrderConfig.java
// =============================================================================

package com.example.order;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** 纯逻辑类（无 @Component）显式装配为 Spring Bean——保持构造器注入纪律 */
@Configuration
public class OrderConfig {

    @Bean
    public DedupStore dedupStore() {
        return new DedupStore(60_000); // TTL 窗口 60s（生产建议 Redis + 可配置 TTL）
    }

    @Bean
    public OrderStore orderStore() {
        return new OrderStore();
    }
}

// =============================================================================
// src/main/java/com/example/order/OrderCreatedConsumer.java
// =============================================================================

package com.example.order;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;

/**
 * 异步订单处理消费者：ack-mode=MANUAL（application.yml 同 examples/ex02）。
 * 失败策略选型（两种都要能说清）：
 *   a) JSON 解析失败这类「消息本身坏」——记日志 + 继续 ack：坏消息重试一万次还是坏的，别卡住消费者，
 *      由监控/死信在更高的层收（练习 3 处理「重试耗尽进死信」）；
 *   b) 业务瞬时失败（下游 5xx）——抛异常交给容器重试（spring-kafka 默认重试后放弃），或自己投重试 topic。
 * 本实现演示 a：解析失败 ack 跳过，解析成功但建单被去重挡下也 ack（都算「处理完」）。
 */
@Component
public class OrderCreatedConsumer {

    private static final Logger log = LoggerFactory.getLogger(OrderCreatedConsumer.class);

    private final ObjectMapper objectMapper;
    private final DedupStore dedup;
    private final OrderStore store;

    public OrderCreatedConsumer(ObjectMapper objectMapper, DedupStore dedup, OrderStore store) {
        this.objectMapper = objectMapper;
        this.dedup = dedup;
        this.store = store;
    }

    @KafkaListener(topics = "orders", groupId = "async-order-group")
    public void onMessage(org.apache.kafka.clients.consumer.ConsumerRecord<String, String> record,
                          Acknowledgment ack) {
        try {
            OrderEvent event = objectMapper.readValue(record.value(), OrderEvent.class);
            if (dedup.tryAcquire(event.orderId())) {          // 第一层：TTL 去重表挡窗口内重复
                boolean created = store.tryCreate(event);     // 第二层：唯一键兜底（迟到的重放也进不来）
                log.info("orderId={} created={} totalCreated={}",
                        event.orderId(), created, store.createdCount());
            } else {
                log.warn("duplicate ignored orderId={}", event.orderId());
            }
        } catch (Exception e) {
            // 消息本身坏（解析失败等）：记日志 + ack 跳过（策略 a，见类注释）
            log.error("bad message skipped partition={} offset={} err={}",
                    record.partition(), record.offset(), e.getMessage());
        }
        ack.acknowledge();
    }
}

// =============================================================================
// src/test/java/com/example/order/AsyncOrderTest.java（离线可跑，无需 Kafka）
// =============================================================================

package com.example.order;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** 纯 JUnit：验证「幂等建单」语义，不需要 Kafka broker（未在本环境验证） */
class AsyncOrderTest {

    private final OrderStore store = new OrderStore();

    @Test
    void sameOrderIdDeliveredTwiceCreatesOnce() {
        OrderEvent event = new OrderEvent("order-1001", "user-1", 99);
        assertTrue(store.tryCreate(event), "首次投递应建单");
        assertFalse(store.tryCreate(event), "同一 orderId 重复投递不应二次建单");
        assertEquals(1, store.createdCount());
    }

    @Test
    void differentOrderIdsCreateIndependently() {
        store.tryCreate(new OrderEvent("order-1", "user-1", 10));
        store.tryCreate(new OrderEvent("order-2", "user-1", 20));
        assertEquals(2, store.createdCount());
    }

    @Test
    void dedupStoreExpiredWindowReleasesThenUniqueKeyGuards() throws InterruptedException {
        DedupStore dedup = new DedupStore(50); // 50ms 窗口，测试可等
        assertTrue(dedup.tryAcquire("order-1001"), "首次见放行");
        assertFalse(dedup.tryAcquire("order-1001"), "窗口内重复被挡");
        Thread.sleep(80);                       // 等窗口过期
        assertTrue(dedup.tryAcquire("order-1001"), "过期后重放放行 —— 唯一键兜底是必须的");
        store.tryCreate(new OrderEvent("order-1001", "user-1", 99));
        assertFalse(store.tryCreate(new OrderEvent("order-1001", "user-1", 99)),
                "即便去重表放行了，OrderStore 唯一键仍挡下重复建单");
        assertEquals(1, store.createdCount());
    }
}
