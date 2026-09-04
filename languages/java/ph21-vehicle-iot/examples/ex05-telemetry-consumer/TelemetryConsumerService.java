// examples/ex05-telemetry-consumer/TelemetryConsumerService.java —— 消费服务：poll + 幂等 + 提交 offset
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//
// 教学点(兑现 ph17 技能)：消费者三件事缺一不可——
//   1. 自己维护 nextOffset：Kafka 不会主动推消息，poll 的起点由消费者决定；
//   2. 幂等处理：崩溃后重放是 Kafka 的常态(至少一次语义)，业务侧用「键去重」把重复消费
//      变成无害(本类用 ConcurrentHashMap 记已处理键，真实系统常落 Redis 或 DB 唯一索引)；
//   3. 处理成功才提交 offset：绝不能「先提交后处理」，否则崩溃即丢数据。
import java.util.concurrent.ConcurrentHashMap;

public final class TelemetryConsumerService {
    private final MiniKafka kafka;
    private final ConcurrentHashMap<String, Boolean> processed = new ConcurrentHashMap<>();
    private final int batchSize;
    private long nextOffset;
    private long processedTotal;

    public TelemetryConsumerService(MiniKafka kafka, long startOffset, int batchSize) {
        this.kafka = kafka;
        this.nextOffset = startOffset;
        this.batchSize = batchSize;
    }

    /** 拉一批并处理；返回本批新增处理数(重复消息返回 0)。 */
    public long pollAndProcess() {
        MiniKafka.ConsumedResult batch = kafka.readFrom(nextOffset, batchSize);
        long newlyProcessed = 0;
        for (TelemetryMessage msg : batch.messages()) {
            // putIfAbsent 原子去重：已见过的键返回已有值，等于没处理
            if (processed.putIfAbsent(msg.idempotencyKey(), Boolean.TRUE) == null) {
                processMsg(msg);          // 真实系统：落库/更新状态缓存/触发规则(见 ex03/ex04)
                newlyProcessed++;
            }
        }
        nextOffset = batch.nextOffset();  // 处理成功整批，才把 offset 推进到批尾
        processedTotal += newlyProcessed;
        return newlyProcessed;
    }

    private void processMsg(TelemetryMessage msg) {
        // 演示用的下游：真实形态是把 soc 写进 ex03 的状态缓存 + 触发 ex04 规则引擎
        Thread.onSpinWait();
    }

    public long nextOffset()     { return nextOffset; }
    public long processedTotal() { return processedTotal; }

    /** 模拟崩溃后从已提交的旧 offset 恢复(可能重放一批已处理消息，靠幂等兜底)。 */
    void resetTo(long offset) { this.nextOffset = offset; }
}
