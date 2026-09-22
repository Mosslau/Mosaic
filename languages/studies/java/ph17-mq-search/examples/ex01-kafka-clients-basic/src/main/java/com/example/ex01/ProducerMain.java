package com.example.ex01;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringSerializer;

import java.util.Map;
import java.util.Properties;

/**
 * Kafka 生产者骨架（主文档 3.2/3.3）：acks=all + 幂等 + 重试，send 异步 + 回调观察写入结果。
 * 验证环境：OpenJDK 17 + Maven 3.9 + kafka-clients 3.7.0（pom 见本工程）。
 * 验证命令（需本地 Kafka，docker compose 见 examples/README.md）：
 *   mvn -o -Dmaven.repo.local=/tmp/m2clone spring-boot:run -Dspring-boot.run.main-class=com.example.ex01.ProducerMain
 * 验证状态：未在本环境验证（需要 Kafka broker）。
 */
public class ProducerMain {

    private static final String TOPIC = "orders";
    private static final ObjectMapper JSON = new ObjectMapper();

    public static void main(String[] args) throws Exception {
        Properties props = new Properties();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());

        // 3.3 生产端可靠性三件套：acks=all（等 ISR 全员确认）→ 重试（只治瞬时故障）→ 幂等（重试不产生重复）
        props.put(ProducerConfig.ACKS_CONFIG, "all");
        props.put(ProducerConfig.RETRIES_CONFIG, Integer.MAX_VALUE);
        props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true); // Kafka 3.x 默认开；开则 acks 被强制为 all

        try (KafkaProducer<String, String> producer = new KafkaProducer<>(props)) {
            for (int i = 1; i <= 5; i++) {
                String orderId = "order-" + i;
                String value = JSON.writeValueAsString(Map.of(
                        "orderId", orderId,
                        "userId", "user-" + (i % 3),
                        "amount", 100 * i));
                // key = orderId：同 key 恒进同一分区 → 该订单的事件有序（主文档 3.5）
                producer.send(new ProducerRecord<>(TOPIC, orderId, value), (metadata, e) -> {
                    if (e == null) {
                        System.out.printf("sent key=%s -> topic=%s partition=%d offset=%d%n",
                                orderId, metadata.topic(), metadata.partition(), metadata.offset());
                    } else {
                        System.err.printf("send failed key=%s err=%s%n", orderId, e.getMessage());
                    }
                });
                Thread.sleep(200); // 慢一点，方便看回调
            }
            producer.flush(); // try-with-resources 关闭前也会 flush；显式一次便于观察
        }
        System.out.println("producer done: 已发送 5 条订单事件到 topic " + TOPIC);
    }
}
