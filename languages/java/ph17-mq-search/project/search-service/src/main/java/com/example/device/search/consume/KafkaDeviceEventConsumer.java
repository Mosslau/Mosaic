// 验证环境：OpenJDK 17 + Maven 3.9 + Spring Boot 3.3.0 + spring-kafka 3.2.0
// 构建/运行命令见 search-service/pom.xml 与 project/README.md（模式 B 需 docker compose 起 Kafka）
// 验证状态：未在本环境验证
package com.example.device.search.consume;

import com.example.device.search.domain.DeviceEvent;
import com.example.device.search.index.EventIndexer;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;

/**
 * 设备事件消费者：topic device-events（key=sn，分区内按设备有序）-> (sn,seq) 去重 -> 写索引 -> 手动 ack。
 * 链路语义（主文档 3.3/3.10）：
 *  - 先处理（去重 + 索引）再 ack -> at-least-once；崩溃重启会重复消费，靠 DeviceEventDedup 幂等；
 *  - 索引失败（如 ES 不可用）不 ack 并抛异常交给 spring-kafka 容器重试——重试耗尽的生产形态是死信
 *    （exercises 练习 3 已实现，本骨架用容器默认重试简化）；
 *  - 坏消息（JSON 解析失败）记录后 ack 跳过：重试一万次还是坏的，别卡住分区（sol-01 同样的取舍）。
 */
@Component
public class KafkaDeviceEventConsumer {

    private static final Logger log = LoggerFactory.getLogger(KafkaDeviceEventConsumer.class);

    private final ObjectMapper objectMapper;
    private final DeviceEventDedup dedup;
    private final EventIndexer indexer;

    public KafkaDeviceEventConsumer(ObjectMapper objectMapper, DeviceEventDedup dedup, EventIndexer indexer) {
        this.objectMapper = objectMapper;
        this.dedup = dedup;
        this.indexer = indexer;
    }

    @KafkaListener(topics = "device-events", groupId = "device-search-group")
    public void onMessage(ConsumerRecord<String, String> record, Acknowledgment ack) {
        try {
            DeviceEvent event = objectMapper.readValue(record.value(), DeviceEvent.class);
            if (dedup.tryAccept(event.sn(), event.seq())) {
                indexer.index(event);
                log.info("indexed sn={} seq={} type={} severity={} acceptedTotal={}",
                        event.sn(), event.seq(), event.type(), event.severity(), dedup.acceptedCount());
            } else {
                log.warn("duplicate or stale dropped sn={} seq={}（(sn,seq) 幂等）", event.sn(), event.seq());
            }
            ack.acknowledge();
        } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
            // 坏消息：记录 + ack 跳过（解析不了的事件没有重试价值）
            log.error("bad event skipped partition={} offset={} err={}",
                    record.partition(), record.offset(), e.getMessage());
            ack.acknowledge();
        } catch (Exception e) {
            // 索引失败（ES 不可用等）：不 ack，抛给容器重试（默认错误处理器；生产接死信，见类注释）
            log.error("index failed partition={} offset={} err={}", record.partition(), record.offset(), e.getMessage());
            throw new IllegalStateException("index failed", e);
        }
    }
}
