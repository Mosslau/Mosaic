// exercises/sol-04-telemetry-consumer/MemoryKafka.java —— 多分区内存版 Kafka(参考实现)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-sol *.java
//
// 题目要求(roadmap §21 练习「Kafka 遥测消费服务」)：
//   - 一个多分区 topic：按 VIN 哈希决定分区(保证同车同分区、有序)；
//   - 消费组：多个消费者分摊分区(每个分区同一时刻只被一个消费者读)；
//   - 每消费者维护自己的 nextOffset 与已提交 offset，可监控 lag；
//   - 幂等：分区重放/重复投递不导致重复入库。
// 参考实现用「每分区一个 ArrayList + long 索引」表达 offset(与 ex05 同源，扩展成多分区)。
import java.util.ArrayList;
import java.util.List;

public final class MemoryKafka {
    public static final int PARTITIONS = 4;

    /** 每个分区的顺序日志：下标即 offset。 */
    private final List<List<TelemetryMsg>> logs = new ArrayList<>();

    public MemoryKafka() {
        for (int i = 0; i < PARTITIONS; i++) {
            logs.add(new ArrayList<>());
        }
    }

    /** 生产：按 VIN 哈希分区(同 VIN 永远同一分区，保序)。 */
    public int produce(TelemetryMsg msg) {
        int partition = Math.floorMod(msg.vin().hashCode(), PARTITIONS);
        logs.get(partition).add(msg);
        return partition;
    }

    public List<TelemetryMsg> read(int partition, long fromOffset, int max) {
        List<TelemetryMsg> log = logs.get(partition);
        int from = (int) Math.min(fromOffset, log.size());
        int to = (int) Math.min(from + max, log.size());
        return new ArrayList<>(log.subList(from, to));
    }

    public long logEndOffset(int partition) {
        return logs.get(partition).size();
    }
}
