package com.example.device.emitter;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringSerializer;

import java.util.Properties;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 模拟设备群：按 sn-001..sn-010 循环生成设备事件，key=sn 发往 topic device-events。
 * 教学点：
 *  1) key=sn -> 同设备恒进同分区 -> 单设备事件有序（主文档 3.5），不同设备并行；
 *  2) 可靠性配置同 examples/ex01：acks=all + 幂等 + 重试（3.3）；
 *  3) 每台设备 seq 自增且连续——消费端靠 (sn,seq) 幂等 + 回退丢弃（见 search-service）。
 * 验证环境：OpenJDK 17 + Maven 3.9 + kafka-clients 3.7.0（pom 见本模块）。
 * 运行命令（需 Kafka，project/docker-compose.yml；在 project/ 根目录执行）：
 *   mvn -o -Dmaven.repo.local=/tmp/m2clone -pl device-emitter exec:java \
 *     -Dexec.mainClass=com.example.device.emitter.DeviceEmitter -Dexec.args="100"
 *   （args 第一个数字 = 发送条数，默认 100；联网环境去掉 -o 参数）
 * 验证状态：未在本环境验证（需要 Kafka broker）。
 */
public final class DeviceEmitter {

    private static final String TOPIC = "device-events";
    private static final String BOOTSTRAP = System.getProperty("bootstrap.servers", "localhost:9092");
    private static final String[] TYPES = {"alarm", "heartbeat", "location"};
    private static final String[] SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"};
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final AtomicLong seqCounter = new AtomicLong(1);

    private DeviceEmitter() {
    }

    public static void main(String[] args) throws Exception {
        int count = args.length > 0 ? Integer.parseInt(args[0]) : 100;

        Properties props = new Properties();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, BOOTSTRAP);
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        props.put(ProducerConfig.ACKS_CONFIG, "all");
        props.put(ProducerConfig.RETRIES_CONFIG, Integer.MAX_VALUE);
        props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);

        try (KafkaProducer<String, String> producer = new KafkaProducer<>(props)) {
            for (int i = 0; i < count; i++) {
                String sn = "sn-" + String.format("%03d", (i % 10) + 1); // sn-001..sn-010 循环
                String type = TYPES[i % TYPES.length];
                String severity = SEVERITIES[(i / 3) % SEVERITIES.length];
                DeviceEvent event = new DeviceEvent(
                        UUID.randomUUID().toString(),
                        sn,
                        seqCounter.getAndIncrement(), // 每设备独立序号：真实设备侧应各自维护，这里用全局近似
                        type,
                        severity,
                        switch (type) {
                            case "alarm" -> "component low / overheat on " + sn;
                            case "heartbeat" -> "heartbeat ok from " + sn;
                            default -> "location report from " + sn;
                        },
                        System.currentTimeMillis());
                String json = JSON.writeValueAsString(event);
                producer.send(new ProducerRecord<>(TOPIC, sn, json), (metadata, e) -> {
                    if (e != null) {
                        System.err.printf("send failed sn=%s err=%s%n", sn, e.getMessage());
                    }
                });
                if (i % 10 == 0) {
                    producer.flush(); // 每 10 条 flush 一次，便于观察投递进度
                }
            }
            System.out.println("emitter done: sent " + count + " events to " + TOPIC + " (key=sn)");
        }
    }
}
