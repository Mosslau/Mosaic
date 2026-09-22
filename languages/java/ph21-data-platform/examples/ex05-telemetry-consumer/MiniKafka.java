// examples/ex05-telemetry-consumer/MiniKafka.java —— 内存版 Kafka：分区顺序日志 + offset 语义
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//
// 教学点：Kafka 的核心心智不是「队列」而是「按 offset 可重放的分区日志」。本类用 ArrayList
// 复刻最小语义——produce 追加、consumer 从某 offset 读到 logEndOffset、offset 永不回退。
// 真实 Kafka 的接入不依赖本类：consumer 用 kafka-clients 的 poll/commit(生产代码见主文档 3.3，
// 本机无 broker 未验证)。本内存版让「消费-幂等-重放」逻辑可离线单测。
import java.util.ArrayList;
import java.util.List;

public final class MiniKafka {
    private final List<TelemetryMessage> log = new ArrayList<>();   // 单个分区，按序追加

    /** 写入一批消息，返回这批消息的起始 offset。 */
    public long produce(List<TelemetryMessage> batch) {
        long firstOffset = log.size();
        log.addAll(batch);
        return firstOffset;
    }

    /** 从 fromOffset 读到 logEndOffset，返回 (可见消息, 下一个要读的 offset)。 */
    public ConsumedResult readFrom(long fromOffset, int maxRecords) {
        int from = (int) Math.min(fromOffset, log.size());
        int to = (int) Math.min(from + maxRecords, log.size());
        return new ConsumedResult(log.subList(from, to), to);
    }

    /** 当前 log 末尾 offset(下一条消息将被写入的位置)。 */
    public long logEndOffset() { return log.size(); }

    /** 消费一批的结果：消息 + 这批之后应提交的 offset(=logEndOffset)。 */
    record ConsumedResult(List<TelemetryMessage> messages, long nextOffset) { }
}
