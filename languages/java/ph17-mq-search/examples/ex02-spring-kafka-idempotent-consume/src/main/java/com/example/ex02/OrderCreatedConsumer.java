// 验证环境：OpenJDK 17 + Maven 3.9 + spring-kafka 3.2.0（pom 见本模块）；构建/运行命令见 examples/README.md 与主文档 3.2/3.4
// 验证状态：未在本环境验证（需本地 Kafka，docker compose 见 examples/）
package com.example.ex02;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 订单创建事件消费者（主文档 3.2/3.3/3.4）：
 *  1) ack-mode=MANUAL：处理成功才 ack.acknowledge() —— at-least-once（application.yml 配 spring.kafka.listener.ack-mode: manual）；
 *  2) DedupStore 占位成功才建单 —— 同一 orderId 重复投递只建单一次（去重表方案）；
 *  3) 建单计数用 AtomicInteger 暴露给日志，便于观察「重复投递被挡下」。
 */
@Component
public class OrderCreatedConsumer {

    private static final Logger log = LoggerFactory.getLogger(OrderCreatedConsumer.class);

    private final ObjectMapper objectMapper;
    private final DedupStore dedup;
    private final Map<String, String> orders = new ConcurrentHashMap<>();
    private final AtomicInteger created = new AtomicInteger();

    public OrderCreatedConsumer(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
        this.dedup = new DedupStore(60_000); // TTL 窗口 60s
    }

    @KafkaListener(topics = "orders", groupId = "order-created-group")
    public void onMessage(org.apache.kafka.clients.consumer.ConsumerRecord<String, String> record,
                          Acknowledgment ack) throws Exception {
        OrderEvent event = objectMapper.readValue(record.value(), OrderEvent.class);
        if (dedup.tryAcquire(event.orderId())) {
            orders.put(event.orderId(), event.userId()); // 建单：真实系统写数据库 + 唯一约束兜底
            log.info("created orderId={} userId={} totalCreated={}",
                    event.orderId(), event.userId(), created.incrementAndGet());
        } else {
            log.warn("duplicate ignored orderId={}（去重表窗口内重放）", event.orderId());
        }
        ack.acknowledge(); // 处理完（无论新建还是去重跳过）才提交 offset
    }
}
