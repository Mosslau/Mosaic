// exercises/sol-02-vehicle-telemetry-consume.java —— 练习 2 参考实现：车辆数据消费（roadmap ph17 练习：车辆数据消费）
// 验证环境：OpenJDK 17 + Maven 3.9 + Spring Boot 3.3.0 + spring-kafka 3.2.0（pom 复制 examples/ex02 的）
// 验证状态：未在本环境验证。纯 JUnit 部分（PerVehicleStatsTest）理论上 `mvn -o -Dmaven.repo.local=/tmp/m2clone test`
//   可离线跑（pom 需追加 test-scope spring-boot-starter-test）；Kafka 链路需先起 Kafka（examples/docker-compose.yml）
//   + 造数（见文末命令），未在本环境实测。
// 教学点：key=sn 恒进同分区 -> 单车顺序（主文档 3.5）；(sn,seq) 幂等 + 旧 seq 丢弃挡「重复 + 迟到」（3.4/3.5）；
//   消费者数不能超过分区数（4.2 重平衡）；聚合状态在单实例内存（分布式状态外置是进阶话题）。

// =============================================================================
// src/main/java/com/example/vehicle/Telemetry.java
// =============================================================================

package com.example.vehicle;

/** 车辆遥测点（生产由车机/接入服务写入 topic vehicle.telemetry，key=sn） */
public record Telemetry(String sn, long seq, double speed, int battery, long ts) {
}

// =============================================================================
// src/main/java/com/example/vehicle/VehicleStats.java
// =============================================================================

package com.example.vehicle;

/** 单车滚动聚合结果（只读视图） */
public record VehicleStats(String sn, double avgSpeedLast5, double maxSpeed, int battery, long lastTs) {
}

// =============================================================================
// src/main/java/com/example/vehicle/PerVehicleStats.java
// =============================================================================

package com.example.vehicle;

import java.util.ArrayDeque;
import java.util.Deque;

/**
 * 单车状态聚合器：只接受「顺序且去重后」的遥测（由消费端保证，见 VehicleStatsEngine.accept），
 * 内部维护最近 5 条速度窗口。注意：乱序/重复的过滤不在本类做——状态机只吃有序输入，入口守门更简单。
 */
final class PerVehicleStats {

    private static final int WINDOW = 5;

    private final String sn;
    private final Deque<Double> speeds = new ArrayDeque<>();
    private long lastSeq = -1;
    private double maxSpeed = 0;
    private int battery;
    private long lastTs;

    PerVehicleStats(String sn) {
        this.sn = sn;
    }

    /** 仅当 seq 严格递增时接受（seq <= lastSeq 的迟到/重复由上层丢弃） */
    boolean accept(Telemetry t) {
        if (t.seq() <= lastSeq) {
            return false;
        }
        lastSeq = t.seq();
        speeds.addLast(t.speed());
        if (speeds.size() > WINDOW) {
            speeds.removeFirst();
        }
        maxSpeed = Math.max(maxSpeed, t.speed());
        battery = t.battery();
        lastTs = t.ts();
        return true;
    }

    VehicleStats snapshot() {
        double avg = speeds.stream().mapToDouble(Double::doubleValue).average().orElse(0);
        return new VehicleStats(sn, avg, maxSpeed, battery, lastTs);
    }
}

// =============================================================================
// src/main/java/com/example/vehicle/VehicleStatsEngine.java
// =============================================================================

package com.example.vehicle;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 全车辆聚合引擎（单实例内存）：sn -> 单车状态。消费端先做 (sn,seq) 幂等/乱序过滤再喂进来。
 * 生产进阶：多实例时状态要外置（Redis 哈希 / 状态存储），本练习只做单实例语义。
 */
public final class VehicleStatsEngine {

    private final Map<String, PerVehicleStats> perVehicle = new ConcurrentHashMap<>();

    /** 返回 true = 该条被接受（新 seq），false = 重复或迟到（seq 不增） */
    public boolean accept(Telemetry t) {
        return perVehicle.computeIfAbsent(t.sn(), PerVehicleStats::new).accept(t);
    }

    public VehicleStats snapshot(String sn) {
        PerVehicleStats stats = perVehicle.get(sn);
        return stats == null ? null : stats.snapshot();
    }
}

// =============================================================================
// src/main/java/com/example/vehicle/TelemetryConsumer.java
// =============================================================================

package com.example.vehicle;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 车辆遥测消费者：group telemetry-aggregator；消息 key=sn（生产者按 sn 设 key，主文档 3.5）。
 * 单车顺序假设的前提链：key=sn 进同分区 -> 组内分区由单消费者拉取 -> 监听方法内串行处理 -> 顺序保留。
 * 若将来消费端开多线程并发处理同一分区，顺序会被破坏——需要按 sn 再分桶串行化（本练习不做）。
 */
@Component
public class TelemetryConsumer {

    private static final Logger log = LoggerFactory.getLogger(TelemetryConsumer.class);
    private static final double OVERSPEED_KMH = 120.0;

    private final ObjectMapper objectMapper;
    private final VehicleStatsEngine engine;

    /** (sn,seq) 已见集合——内存去重只挡「本次进程生命周期内的重复」；生产要跨重启/多实例（Redis/DB） */
    private final Set<String> seen = ConcurrentHashMap.newKeySet();

    public TelemetryConsumer(ObjectMapper objectMapper, VehicleStatsEngine engine) {
        this.objectMapper = objectMapper;
        this.engine = engine;
    }

    @KafkaListener(topics = "vehicle.telemetry", groupId = "telemetry-aggregator")
    public void onMessage(org.apache.kafka.clients.consumer.ConsumerRecord<String, String> record,
                          Acknowledgment ack) throws Exception {
        Telemetry t = objectMapper.readValue(record.value(), Telemetry.class);
        if (t.sn() == null || !t.sn().equals(record.key())) {
            log.warn("sn mismatch key={} body={}", record.key(), t.sn()); // key 与 body 不一致：路由坏信号
        }
        if (seen.add(t.sn() + ":" + t.seq())) {           // (sn,seq) 幂等：重复投递只进一次
            boolean accepted = engine.accept(t);          // 引擎内再挡一次 seq 回退（迟到旧数据）
            if (accepted && t.speed() > OVERSPEED_KMH) {
                // 超速：真实系统在这里发告警事件（练习 3 的 alarm.alerts 由此而来）
                log.warn("OVERSPEED sn={} seq={} speed={} km/h", t.sn(), t.seq(), t.speed());
            }
        }
        VehicleStats stats = engine.snapshot(t.sn());
        log.info("sn={} seq={} speed={} -> avgLast5={} max={}",
                t.sn(), t.seq(), t.speed(), stats == null ? 0 : stats.avgSpeedLast5(),
                stats == null ? 0 : stats.maxSpeed());
        ack.acknowledge();                                // 先处理（含去重判定）再提交：at-least-once
    }
}

// =============================================================================
// src/main/java/com/example/vehicle/VehicleConfig.java
// =============================================================================

package com.example.vehicle;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class VehicleConfig {

    @Bean
    public VehicleStatsEngine vehicleStatsEngine() {
        return new VehicleStatsEngine();
    }
}

// =============================================================================
// src/test/java/com/example/vehicle/PerVehicleStatsTest.java（离线可跑，无需 Kafka）
// =============================================================================

package com.example.vehicle;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** 单车聚合语义（未在本环境验证） */
class PerVehicleStatsTest {

    private final VehicleStatsEngine engine = new VehicleStatsEngine();

    @Test
    void duplicateAndLateSequenceAreIgnored() {
        Telemetry t1 = new Telemetry("sn-A", 1, 100, 80, 1000);
        Telemetry dup = new Telemetry("sn-A", 1, 999, 80, 1001);   // 重复投递（同 seq）
        Telemetry late = new Telemetry("sn-A", 0, 200, 80, 900);   // 迟到旧数据（seq 回退）
        assertTrue(engine.accept(t1), "新 seq 应被接受");
        assertFalse(engine.accept(dup), "同 seq 重复应被丢弃（不重复计入统计）");
        assertFalse(engine.accept(late), "旧 seq 迟到应被丢弃（不破坏统计）");
        assertEquals(100, engine.snapshot("sn-A").avgSpeedLast5(), 1e-6,
                "重复与迟到都被挡下，平均车速只按有效点算");
    }

    @Test
    void avgSpeedUsesLastFiveReadings() {
        int[] speeds = {60, 70, 80, 90, 100, 110};
        for (int i = 0; i < speeds.length; i++) {
            engine.accept(new Telemetry("sn-B", i + 1, speeds[i], 90, i * 100L));
        }
        // 6 条进来窗口只留最近 5 条 = 70,80,90,100,110 -> 均值 90；60 被挤出
        assertEquals(90.0, engine.snapshot("sn-B").avgSpeedLast5(), 1e-6);
        assertEquals(110.0, engine.snapshot("sn-B").maxSpeed(), 1e-6);
    }

    @Test
    void vehiclesAreIsolated() {
        engine.accept(new Telemetry("sn-X", 1, 50, 100, 1));
        engine.accept(new Telemetry("sn-Y", 1, 200, 60, 1));
        assertEquals(50.0, engine.snapshot("sn-X").avgSpeedLast5(), 1e-6);
        assertEquals(200.0, engine.snapshot("sn-Y").maxSpeed(), 1e-6, "每车独立聚合，互不串扰");
    }

    @Test
    void overspeedThresholdIsOnConsumerSide() {
        // 超速判定在 TelemetryConsumer（OVERSPEED_KMH=120），引擎只算统计；
        // 这里验证引擎对 121 也正常聚合（阈值逻辑属消费端，见 TelemetryConsumer）
        engine.accept(new Telemetry("sn-Z", 1, 121, 90, 1));
        assertEquals(121.0, engine.snapshot("sn-Z").maxSpeed(), 1e-6);
    }
}

// =============================================================================
// 造数与手工验证（需 Kafka，未在本环境验证）
// =============================================================================
// 1) 建 topic（3 分区，便于观察多消费者并行；单消费者演示 1 分区也够）：
//    docker exec -it mqs-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 \
//      --create --topic vehicle.telemetry --partitions 3 --replication-factor 1
// 2) 造数：key=sn（冒号分隔 key/value），同 sn 连续 seq：
//    docker exec -it mqs-kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 \
//      --topic vehicle.telemetry --property parse.key=true --property key.separator=:
//    输入示例（每行一条）：sn-A:{"sn":"sn-A","seq":1,"speed":100,"battery":80,"ts":1700000000000}
// 3) 观察：同一 sn 的消息始终在同一个 partition；seq 重复/回退被 seen 与引擎双层挡下。
