// project/src/dataplat/MetricBus.java —— 指标总线(内存版 Kafka：多分区 + offset)
package dataplat;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/dataplat/*.java
//
// 数据链路的中间地带：接入服务校验后投递，消费服务按分区顺序读。
// 真 Kafka 用 kafka-clients(未在本环境验证)，本类保留三个关键语义：
//   按 SOURCE_ID 哈希分区(同g同分区保序)、append-only 日志、offset 定位。
import java.util.ArrayList;
import java.util.List;

public final class MetricBus {
    public static final int PARTITIONS = 8;

    private final List<List<MetricFrame>> logs = new ArrayList<>();

    public MetricBus() {
        for (int i = 0; i < PARTITIONS; i++) {
            logs.add(new ArrayList<>());
        }
    }

    /** 生产：返回落入的分区号(同 SOURCE_ID 永远同分区)。 */
    public int produce(MetricFrame frame) {
        int partition = Math.floorMod(frame.sourceId().hashCode(), PARTITIONS);
        synchronized (logs.get(partition)) {
            logs.get(partition).add(frame);
        }
        return partition;
    }

    /** 消费：读某分区 [fromOffset, logEnd) 的帧。调用方保证不与 produce 并发。 */
    public List<MetricFrame> read(int partition, long fromOffset) {
        synchronized (logs.get(partition)) {
            List<MetricFrame> log = logs.get(partition);
            return List.copyOf(log.subList((int) Math.min(fromOffset, log.size()), log.size()));
        }
    }

    public long logEnd(int partition) {
        synchronized (logs.get(partition)) {
            return logs.get(partition).size();
        }
    }

    public long totalProduced() {
        long sum = 0;
        for (int p = 0; p < PARTITIONS; p++) {
            sum += logEnd(p);
        }
        return sum;
    }
}
