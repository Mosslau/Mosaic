// project/src/vehicleiot/TelemetryConsumer.java —— Kafka 遥测消费服务(单消费者遍历各分区)
package vehicleiot;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/vehicleiot/*.java
//
// 消费端把总线里每条干净帧同步到三个下游：状态缓存(最新帧)、轨迹(按车历史)、
// 设备在线状态；并在状态更新后立刻喂规则引擎(告警只看最新状态，避免重复告警)。
// offset 推进语义：读到哪、commit 到哪，落后即积压(与 examples/ex05 同源)。
public final class TelemetryConsumer {
    private final TelemetryBus bus;
    private final DeviceRegistry registry;
    private final VehicleStateCache stateCache;
    private final TrackStore trackStore;
    private final AlertEngine alertEngine;
    private final long[] nextOffsetByPartition = new long[TelemetryBus.PARTITIONS];
    private long processed;

    public TelemetryConsumer(TelemetryBus bus, DeviceRegistry registry, VehicleStateCache stateCache,
                             TrackStore trackStore, AlertEngine alertEngine) {
        this.bus = bus;
        this.registry = registry;
        this.stateCache = stateCache;
        this.trackStore = trackStore;
        this.alertEngine = alertEngine;
    }

    /** 一次性把当前所有分区的积压消费完；返回本次新增处理条数。 */
    public long drain() {
        long newly = 0;
        for (int p = 0; p < TelemetryBus.PARTITIONS; p++) {
            for (TelemetryFrame f : bus.read(p, nextOffsetByPartition[p])) {
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
        for (int p = 0; p < TelemetryBus.PARTITIONS; p++) {
            sum += bus.logEnd(p) - nextOffsetByPartition[p];
        }
        return sum;
    }

    public long processed() { return processed; }

    private void apply(TelemetryFrame f) {
        registry.markOnline(f.vin());                 // 有遥测即视为在线
        stateCache.update(f);                         // ① 最新状态
        trackStore.append(f);                         // ② 轨迹历史
        VehicleStateCache.VehicleState latest = stateCache.latest(f.vin());
        if (latest != null && latest.seq() == f.seq()) {
            alertEngine.evaluate(latest);             // ③ 只对刚更新的最新状态跑规则
        }
    }
}
