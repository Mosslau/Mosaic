// project/src/dataplat/MetricConsumer.java —— Kafka 指标消费服务(单消费者遍历各分区)
package dataplat;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/dataplat/*.java
//
// 消费端把总线里每条干净帧同步到三个下游：状态缓存(最新帧)、作业历史(按数据源历史)、
// 节点在线状态；并在状态更新后立刻喂规则引擎(告警只看最新状态，避免重复告警)。
// offset 推进语义：读到哪、commit 到哪，落后即积压(与 examples/ex05 同源)。
public final class MetricConsumer {
    private final MetricBus bus;
    private final NodeRegistry registry;
    private final SourceStateCache stateCache;
    private final JobHistoryStore jobHistoryStore;
    private final AlertEngine alertEngine;
    private final long[] nextOffsetByPartition = new long[MetricBus.PARTITIONS];
    private long processed;

    public MetricConsumer(MetricBus bus, NodeRegistry registry, SourceStateCache stateCache,
                             JobHistoryStore jobHistoryStore, AlertEngine alertEngine) {
        this.bus = bus;
        this.registry = registry;
        this.stateCache = stateCache;
        this.jobHistoryStore = jobHistoryStore;
        this.alertEngine = alertEngine;
    }

    /** 一次性把当前所有分区的积压消费完；返回本次新增处理条数。 */
    public long drain() {
        long newly = 0;
        for (int p = 0; p < MetricBus.PARTITIONS; p++) {
            for (MetricFrame f : bus.read(p, nextOffsetByPartition[p])) {
                apply(f);
                nextOffsetByPartition[p]++;     // 处理完才推进(先处理、后 commit)
                newly++;
            }
        }
        processed += newly;
        return newly;
    }

    /** 剩余未消费(积压)条数：logEnd - 已 commit。 */
    public long lag() {
        long sum = 0;
        for (int p = 0; p < MetricBus.PARTITIONS; p++) {
            sum += bus.logEnd(p) - nextOffsetByPartition[p];
        }
        return sum;
    }

    public long processed() { return processed; }

    private void apply(MetricFrame f) {
        registry.markOnline(f.sourceId());                 // 有指标即视为在线
        stateCache.update(f);                         // ① 最新状态
        jobHistoryStore.append(f);                         // ② 作业历史历史
        SourceStateCache.SourceState latest = stateCache.latest(f.sourceId());
        if (latest != null && latest.seq() == f.seq()) {
            alertEngine.evaluate(latest);             // ③ 只对刚更新的最新状态跑规则
        }
    }
}
