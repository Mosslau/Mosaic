// project/src/dataplat/SourceStateCache.java —— 实时状态缓存(ConcurrentHashMap + compute)
package dataplat;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/dataplat/*.java
//
// 承担「每个数据源的最新一帧」：指标消费端每收到一帧就 update 一次。
// compute 原子段内比较 seq，保证乱序帧不覆盖新帧(与 examples/ex03 同源)。
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

public final class SourceStateCache {
    /** 数据源最新快照(全字段最终态，供告警/运维读)。 */
    public record SourceState(String sourceId, long seq, double cpuPct, double latencyMs, double diskTempC) { }

    private final ConcurrentHashMap<String, SourceState> states = new ConcurrentHashMap<>();

    public void update(MetricFrame f) {
        states.compute(f.sourceId(), (sourceId, cur) -> {
            if (cur == null || f.seq() > cur.seq()) {
                return new SourceState(f.sourceId(), f.seq(), f.cpuPct(), f.latencyMs(), f.diskTempC());
            }
            return cur;
        });
    }

    public SourceState latest(String sourceId) { return states.get(sourceId); }
    public int size() { return states.size(); }
    public List<SourceState> all() {
        return states.values().stream().sorted((a, b) -> a.sourceId().compareTo(b.sourceId())).toList();
    }
}
