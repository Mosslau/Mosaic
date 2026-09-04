// project/src/vehicleiot/VehicleStateCache.java —— 实时状态缓存(ConcurrentHashMap + compute)
package vehicleiot;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/vehicleiot/*.java
//
// 承担「每台车的最新一帧」：遥测消费端每收到一帧就 update 一次。
// compute 原子段内比较 seq，保证乱序帧不覆盖新帧(与 examples/ex03 同源)。
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

public final class VehicleStateCache {
    /** 车辆最新快照(全字段最终态，供告警/运维读)。 */
    public record VehicleState(String vin, long seq, double socPct, double kmh, double motorTempC) { }

    private final ConcurrentHashMap<String, VehicleState> states = new ConcurrentHashMap<>();

    public void update(TelemetryFrame f) {
        states.compute(f.vin(), (vin, cur) -> {
            if (cur == null || f.seq() > cur.seq()) {
                return new VehicleState(f.vin(), f.seq(), f.socPct(), f.kmh(), f.motorTempC());
            }
            return cur;
        });
    }

    public VehicleState latest(String vin) { return states.get(vin); }
    public int size() { return states.size(); }
    public List<VehicleState> all() {
        return states.values().stream().sorted((a, b) -> a.vin().compareTo(b.vin())).toList();
    }
}
