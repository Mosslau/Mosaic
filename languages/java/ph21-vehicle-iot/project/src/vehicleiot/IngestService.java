// project/src/vehicleiot/IngestService.java —— 车辆数据接入服务(同步校验/去重 → 投递总线)
package vehicleiot;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/vehicleiot/*.java
//
// 接入服务的职责边界：解码(已由 TelemetryFrame.decode 完成)、单帧量程校验、
// per-VIN 乱序去重，然后把干净帧 produce 到总线。计数全部原子，多车线程并发安全。
// 生产形态常在此处叠加网关鉴权(连接层)与限流(ph18)，此处聚焦数据正确性。
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

public final class IngestService {
    private final TelemetryBus bus;
    private final ConcurrentHashMap<String, AtomicLong> lastSeqByVin = new ConcurrentHashMap<>();
    private final AtomicLong accepted = new AtomicLong();
    private final AtomicLong rejected = new AtomicLong();
    private final AtomicLong duplicates = new AtomicLong();

    public IngestService(TelemetryBus bus) {
        this.bus = bus;
    }

    /** 上报一行(车端网关按行喂入)；返回是否被接受并投递。 */
    public boolean submit(String rawLine) {
        TelemetryFrame frame = TelemetryFrame.decode(rawLine).orElse(null);
        if (frame == null) {
            rejected.incrementAndGet();
            return false;
        }
        AtomicLong seen = lastSeqByVin.computeIfAbsent(frame.vin(), k -> new AtomicLong());
        long prev = seen.get();
        if (frame.seq() <= prev) {
            duplicates.incrementAndGet();
            return false;
        }
        if (!seen.compareAndSet(prev, frame.seq())) {
            duplicates.incrementAndGet();
            return false;
        }
        bus.produce(frame);
        accepted.incrementAndGet();
        return true;
    }

    public long accepted()   { return accepted.get(); }
    public long rejected()   { return rejected.get(); }
    public long duplicates() { return duplicates.get(); }
}
