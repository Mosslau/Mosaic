// examples/ex05-metrics-consumer/MetricMessage.java —— Kafka 消息体(record)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
import java.util.Objects;

/** 一条指标消息：业务键是 (sourceId, seq)，平台用它做幂等(见消费者去重)。 */
record MetricMessage(String sourceId, long seq, double cpuPct) {
    /** 幂等键：同g同 seq 只该被处理一次。 */
    String idempotencyKey() {
        return sourceId + "#" + seq;
    }
}
