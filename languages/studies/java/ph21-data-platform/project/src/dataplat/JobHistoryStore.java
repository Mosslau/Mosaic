// project/src/dataplat/JobHistoryStore.java —— 作业历史点存储(每个数据源有序点列，供作业历史查询)
package dataplat;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/dataplat/*.java
//
// 作业历史模块独立于状态缓存：缓存要「最新一帧」，作业历史要「按时间的一段历史」。
// 这里用每个数据源一个 ConcurrentLinkedDeque 存最近 K 个点(内存上限约束)，真平台落时序库。
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

public final class JobHistoryStore {
    /** 一个作业历史点：这里用帧的时间序号近似（真实平台记录时间戳 + 任务标识）。 */
    public record TrackPoint(String sourceId, long seq, double latencyMs, double cpuPct) { }

    private static final int MAX_RECORDS_PER_SOURCE = 5000;

    private final ConcurrentHashMap<String, ArrayDeque<TrackPoint>> points = new ConcurrentHashMap<>();

    public void append(MetricFrame f) {
        points.computeIfAbsent(f.sourceId(), k -> new ArrayDeque<>());
        synchronized (points.get(f.sourceId())) {
            ArrayDeque<TrackPoint> deque = points.get(f.sourceId());
            deque.addLast(new TrackPoint(f.sourceId(), f.seq(), f.latencyMs(), f.cpuPct()));
            while (deque.size() > MAX_RECORDS_PER_SOURCE) {
                deque.removeFirst();
            }
        }
    }

    /** 某数据源最近 N 个点(新的在后)。 */
    public List<TrackPoint> recent(String sourceId, int n) {
        ArrayDeque<TrackPoint> deque = points.get(sourceId);
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
