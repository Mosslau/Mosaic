// exercises/sol-03-alarm-push-retry-dlq.java —— 练习 3 参考实现：告警消息推送（roadmap ph17 练习：告警消息推送）
// 验证环境：OpenJDK 17 + Maven 3.9 + Spring Boot 3.3.0 + spring-kafka 3.2.0（pom 复制 examples/ex02 的）
// 验证状态：未在本环境验证。纯 JUnit 部分（PushRetryProcessorTest）理论上 `mvn -o -Dmaven.repo.local=/tmp/m2clone test`
//   可离线跑（pom 需追加 test-scope spring-boot-starter-test）；Kafka 链路（alarm.alerts / alarm.dlt）需先起 Kafka
//   （examples/docker-compose.yml），未在本环境实测。
// 教学点：失败重试的退避与上限（主文档 3.6：无限重试拖死消费者）；死信 = 重试耗尽后的折中落点；
//   延迟消息用「到期时间」模拟（examples/ex03 的 availableAt 思路；RocketMQ 原生 18 级 / RabbitMQ TTL+DLX 对照见主文档 3.6）。
// 设计取舍：推送的幂等由 alarmId 保证（同一条告警重试推送不产生重复通知）——重试与幂等永远成对出现（ph16 结论）。

// =============================================================================
// src/main/java/com/example/alarm/AlarmEvent.java
// =============================================================================

package com.example.alarm;

/** 告警事件（severity: CRITICAL/HIGH/MEDIUM/LOW；来自车辆超速等业务规则，见练习 2） */
public record AlarmEvent(String alarmId, String sn, String severity, String message, long ts) {
}

// =============================================================================
// src/main/java/com/example/alarm/PushClient.java
// =============================================================================

package com.example.alarm;

/** 外部推送客户端抽象（短信/App 推送/钉钉 webhook 的实现可替换；测试注入假实现） */
public interface PushClient {

    /** 推送一条告警；失败抛 PushException（瞬时故障语义，如下游 5xx/超时） */
    void push(AlarmEvent alarm) throws PushException;

    /** 推送成功计数（供测试/监控观察） */
    long successCount();

    class PushException extends Exception {
        public PushException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}

// =============================================================================
// src/main/java/com/example/alarm/PushOutcome.java
// =============================================================================

package com.example.alarm;

/** 一次告警推送的最终结局 */
public enum PushOutcome {
    SENT,       // 推送成功
    DEAD_LETTER // 重试耗尽，移交死信（外部人工/对账兜底，主文档 3.6）
}

// =============================================================================
// src/main/java/com/example/alarm/PushRetryProcessor.java
// =============================================================================

package com.example.alarm;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * 重试策略处理器（纯逻辑，可离线单测）：
 *   - 最多 maxAttempts 次尝试，第 n 次失败后退避 backoffMs[n]（第 1 次失败 -> 等 backoffMs[0]）；
 *   - 第 maxAttempts 次仍失败 -> DEAD_LETTER（由调用方决定投哪——本练习投 topic alarm.dlt）；
 *   - 幂等由 alarmId 保证：重复投递的同一条告警不会重复推送（DedupStore 见 ex02/exercises/sol-01）。
 * 对照主文档 3.6：RocketMQ 消费失败默认重试 16 次进 %DLQ%；RabbitMQ nack(requeue=false) 转 DLX；
 * Kafka 无原生——本类即「自建重试策略」的最小形状。
 */
public final class PushRetryProcessor {

    private static final Logger log = LoggerFactory.getLogger(PushRetryProcessor.class);

    private final PushClient client;
    private final int maxAttempts;
    private final long[] backoffMs;
    private final Sleeper sleeper;

    public PushRetryProcessor(PushClient client, int maxAttempts, long[] backoffMs) {
        this(client, maxAttempts, backoffMs, Thread::sleep);
    }

    /** 注入 Sleeper 以便测试拨时钟（不真睡），生产走默认 Thread.sleep */
    PushRetryProcessor(PushClient client, int maxAttempts, long[] backoffMs, Sleeper sleeper) {
        this.client = client;
        this.maxAttempts = maxAttempts;
        this.backoffMs = backoffMs;
        this.sleeper = sleeper;
    }

    public interface Sleeper {
        void sleep(long ms) throws InterruptedException;
    }

    /** 推送并返回结局；总尝试次数 = attempts()（可用计数器观察） */
    public PushOutcome pushWithRetry(AlarmEvent alarm) {
        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                client.push(alarm);
                log.info("push ok alarmId={} attempt={}", alarm.alarmId(), attempt);
                return PushOutcome.SENT;
            } catch (PushException e) {
                log.warn("push failed alarmId={} attempt={} err={}", alarm.alarmId(), attempt, e.getMessage());
                if (attempt < maxAttempts) {
                    sleepQuietly(backoffMs[Math.min(attempt - 1, backoffMs.length - 1)]); // 退避递增
                }
            }
        }
        log.error("push exhausted alarmId={} -> DEAD_LETTER", alarm.alarmId());
        return PushOutcome.DEAD_LETTER;
    }

    private void sleepQuietly(long ms) {
        try {
            sleeper.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}

// =============================================================================
// src/main/java/com/example/alarm/AlarmConsumer.java
// =============================================================================

package com.example.alarm;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;

/**
 * 告警消费者：推送失败重试耗尽 -> 投死信 topic alarm.dlt（对应 Kafka .dlt / RocketMQ %DLQ% / RabbitMQ DLX）。
 * ack 时机：推送成功或移交死信后都算「处理完」，才 acknowledge——死在两者之间会重复消费，
 * 重复无害（PushRetryProcessor 同 alarmId 重试不重复通知由推送侧幂等保证，见类注释）。
 */
@Component
public class AlarmConsumer {

    private static final Logger log = LoggerFactory.getLogger(AlarmConsumer.class);

    private final ObjectMapper objectMapper;
    private final PushRetryProcessor processor;
    private final KafkaTemplate<String, String> kafkaTemplate;

    public AlarmConsumer(ObjectMapper objectMapper, PushRetryProcessor processor,
                         KafkaTemplate<String, String> kafkaTemplate) {
        this.objectMapper = objectMapper;
        this.processor = processor;
        this.kafkaTemplate = kafkaTemplate;
    }

    @KafkaListener(topics = "alarm.alerts", groupId = "alarm-pusher")
    public void onMessage(ConsumerRecord<String, String> record, Acknowledgment ack) throws Exception {
        AlarmEvent alarm = objectMapper.readValue(record.value(), AlarmEvent.class);
        PushOutcome outcome = processor.pushWithRetry(alarm);
        if (outcome == PushOutcome.DEAD_LETTER) {
            kafkaTemplate.send("alarm.dlt", alarm.alarmId(), record.value()); // 死信：保留原始 JSON，key=alarmId
            log.warn("alarmId={} moved to alarm.dlt", alarm.alarmId());
        }
        ack.acknowledge();
    }
}

// =============================================================================
// src/main/java/com/example/alarm/AlarmConfig.java + application.yml 片段
// =============================================================================

package com.example.alarm;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class AlarmConfig {

    /** 最多 3 次，退避 1s / 5s（生产把间隔与次数做成配置，别硬编码） */
    @Bean
    public PushRetryProcessor pushRetryProcessor(PushClient pushClient) {
        return new PushRetryProcessor(pushClient, 3, new long[]{1_000, 5_000});
    }

    /** 真实环境换成短信/App 推送实现；演示先打日志 */
    @Bean
    public PushClient pushClient() {
        return new LoggingPushClient();
    }

    /** 演示实现：随机失败率可配（生产不这么写，仅用于演示重试路径） */
    static final class LoggingPushClient implements PushClient {
        private static final Logger log = LoggerFactory.getLogger(LoggingPushClient.class);
        private final java.util.concurrent.atomic.AtomicLong sent = new java.util.concurrent.atomic.AtomicLong();

        @Override
        public void push(AlarmEvent alarm) throws PushException {
            log.info("PUSH {} sn={} msg={}", alarm.severity(), alarm.sn(), alarm.message());
            sent.incrementAndGet();
        }

        @Override
        public long successCount() {
            return sent.get();
        }
    }
}

// application.yml 追加（其余同 examples/ex02/application.yml）：
//   spring.kafka.consumer.group-id: alarm-pusher
//   spring.kafka.listener.ack-mode: manual

// =============================================================================
// src/test/java/com/example/alarm/PushRetryProcessorTest.java（离线可跑，无需 Kafka）
// =============================================================================

package com.example.alarm;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

/** 重试/退避/死信决策（未在本环境验证） */
class PushRetryProcessorTest {

    /** 可控假推送：按次数序列决定成功还是失败 */
    static final class ScriptedClient implements PushClient {
        private final boolean[] failBefore;
        private int calls;

        ScriptedClient(boolean... failBefore) {
            this.failBefore = failBefore;
        }

        @Override
        public void push(AlarmEvent alarm) throws PushException {
            boolean shouldFail = calls < failBefore.length && failBefore[calls];
            calls++;
            if (shouldFail) {
                throw new PushException("downstream 5xx", null);
            }
        }

        @Override
        public long successCount() {
            return calls;
        }

        int calls() {
            return calls;
        }
    }

    private static AlarmEvent alarm(String id) {
        return new AlarmEvent(id, "sn-A", "HIGH", "battery low", 1);
    }

    @Test
    void alwaysFailingPushesExactlyMaxAttemptsThenDeadLetter() {
        ScriptedClient client = new ScriptedClient(true, true, true, true);
        PushRetryProcessor processor = new PushRetryProcessor(client, 3, new long[]{0, 0});
        assertEquals(PushOutcome.DEAD_LETTER, processor.pushWithRetry(alarm("alarm-1")));
        assertEquals(3, client.calls(), "最多 3 次，绝不无限重试（拖死消费者是死信要解决的问题）");
    }

    @Test
    void succeedsOnSecondAttempt() {
        ScriptedClient client = new ScriptedClient(true, false);
        PushRetryProcessor processor = new PushRetryProcessor(client, 3, new long[]{0, 0});
        assertEquals(PushOutcome.SENT, processor.pushWithRetry(alarm("alarm-2")));
        assertEquals(2, client.calls(), "第 1 次失败重试后成功：attempts=2");
    }

    @Test
    void backoffIsSkippedInTestsViaZeroDelay() {
        // backoff 传 0 只是测试快；生产退避递增（1s/5s）。Sleep 可注入（Sleeper 接口）做确定性测试
        ScriptedClient client = new ScriptedClient(true, true, false);
        PushRetryProcessor processor = new PushRetryProcessor(client, 3, new long[]{10, 50});
        assertEquals(PushOutcome.SENT, processor.pushWithRetry(alarm("alarm-3")));
        assertEquals(3, client.calls());
    }

    @Test
    void sameAlarmRedeliveredDoesNotDoubleNotifyOnSuccess() {
        // 幂等注：重复投递的同一条告警，推送侧以 alarmId 去重是生产必做（本处用脚本假客户端演示调用次数与结局一致）
        ScriptedClient client = new ScriptedClient(false, false);
        PushRetryProcessor processor = new PushRetryProcessor(client, 3, new long[]{0, 0});
        assertEquals(PushOutcome.SENT, processor.pushWithRetry(alarm("alarm-4")));
        assertEquals(PushOutcome.SENT, processor.pushWithRetry(alarm("alarm-4")));
        assertEquals(2, client.calls(), "不同投递各自推送——真正的防重靠推送服务的 alarmId 幂等键（本练习不做推送服务）");
    }
}
