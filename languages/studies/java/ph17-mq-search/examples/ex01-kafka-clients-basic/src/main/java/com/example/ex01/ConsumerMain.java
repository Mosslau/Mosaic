package com.example.ex01;

import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.consumer.OffsetAndMetadata;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.StringDeserializer;

import java.time.Duration;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Kafka 消费者骨架（主文档 3.2/3.3）：消费组 + 关自动提交 + 全批处理完手动 commitSync（at-least-once）。
 * 教学点：
 *  1) offset 存在 broker 的 __consumer_offsets（按消费组隔离）——组内分区不重复分配；
 *  2) enable.auto.commit=false 后，「处理成功」与「提交 offset」之间崩溃 → 重启重复消费 → 消费端必须幂等（主文档 3.4）；
 *  3) Ctrl+C 优雅退出（shutdown hook），避免强杀触发重平衡（主文档 4.2）。
 * 验证环境：OpenJDK 17 + Maven 3.9 + kafka-clients 3.7.0（pom 见本工程）。
 * 验证命令（需本地 Kafka，docker compose 见 examples/README.md）：
 *   mvn -o -Dmaven.repo.local=/tmp/m2clone spring-boot:run -Dspring-boot.run.main-class=com.example.ex01.ConsumerMain
 * 验证状态：未在本环境验证（需要 Kafka broker）。
 */
public class ConsumerMain {

    private static final String TOPIC = "orders";

    public static void main(String[] args) {
        Properties props = new Properties();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ConsumerConfig.GROUP_ID_CONFIG, "ex01-order-group");            // 消费组：同组共享分区
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");           // 组内无已提交 offset 时从最早读
        props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);               // 关自动提交，提交时机交给业务
        props.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, 10);                    // 每批至多 10 条，便于观察提交节奏

        AtomicBoolean running = new AtomicBoolean(true);
        Runtime.getRuntime().addShutdownHook(new Thread(() -> running.set(false)));

        Map<TopicPartition, OffsetAndMetadata> toCommit = new HashMap<>();
        try (KafkaConsumer<String, String> consumer = new KafkaConsumer<>(props)) {
            consumer.subscribe(List.of(TOPIC));
            while (running.get()) {
                ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(500));
                for (ConsumerRecord<String, String> record : records) {
                    System.out.printf("consume key=%s partition=%d offset=%d value=%s%n",
                            record.key(), record.partition(), record.offset(), record.value());
                    // 处理（这里只打印；真实业务见 ex02 的幂等去重 + 建单）
                    // 提交的是「下一条要读的 offset」= 本条 offset + 1
                    toCommit.put(new TopicPartition(record.topic(), record.partition()),
                            new OffsetAndMetadata(record.offset() + 1));
                }
                if (!records.isEmpty()) {
                    consumer.commitSync(toCommit); // 全批处理完才提交：崩溃最多重复本批 → at-least-once
                    toCommit.clear();
                }
            }
        }
        System.out.println("consumer stopped");
    }
}
