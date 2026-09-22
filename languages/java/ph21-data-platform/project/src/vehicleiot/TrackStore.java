// project/src/vehicleiot/TrackStore.java —— 轨迹点存储(每车有序点列，供轨迹查询)
package vehicleiot;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/vehicleiot/*.java
//
// 轨迹模块独立于状态缓存：缓存要「最新一帧」，轨迹要「按时间的一段历史」。
// 这里用每车一个 ConcurrentLinkedDeque 存最近 K 个点(内存上限约束)，真平台落时序库。
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

public final class TrackStore {
    /** 一个轨迹点：这里用帧的时间序号近似(真实平台记录时间戳 + 经纬度)。 */
    public record TrackPoint(String vin, long seq, double kmh, double socPct) { }

    private static final int MAX_POINTS_PER_VEHICLE = 5000;

    private final ConcurrentHashMap<String, ArrayDeque<TrackPoint>> points = new ConcurrentHashMap<>();

    public void append(TelemetryFrame f) {
        points.computeIfAbsent(f.vin(), k -> new ArrayDeque<>());
        synchronized (points.get(f.vin())) {
            ArrayDeque<TrackPoint> deque = points.get(f.vin());
            deque.addLast(new TrackPoint(f.vin(), f.seq(), f.kmh(), f.socPct()));
            while (deque.size() > MAX_POINTS_PER_VEHICLE) {
                deque.removeFirst();
            }
        }
    }

    /** 某车最近 N 个点(新的在后)。 */
    public List<TrackPoint> recent(String vin, int n) {
        ArrayDeque<TrackPoint> deque = points.get(vin);
        if (deque == null) {
            return List.of();
        }
        synchronized (deque) {
            List<TrackPoint> all = new ArrayList<>(deque);
            int from = Math.max(0, all.size() - n);
            return List.copyOf(all.subList(from, all.size()));
        }
    }

    public int totalPoints() {
        return points.values().stream().mapToInt(d -> { synchronized (d) { return d.size(); } }).sum();
    }
}
