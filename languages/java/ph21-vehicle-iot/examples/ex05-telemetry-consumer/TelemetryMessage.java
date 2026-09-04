// examples/ex05-telemetry-consumer/TelemetryMessage.java —— Kafka 消息体(record)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
import java.util.Objects;

/** 一条遥测消息：业务键是 (vin, seq)，平台用它做幂等(见消费者去重)。 */
record TelemetryMessage(String vin, long seq, double socPct) {
    /** 幂等键：同车同 seq 只该被处理一次。 */
    String idempotencyKey() {
        return vin + "#" + seq;
    }
}
