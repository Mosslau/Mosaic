// examples/ex07-trajectory-query/JobHistoryStore.java —— 作业历史存储：按数据源分桶的有序点集
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//
// 教学点：作业历史查询的本质是「每个 SOURCE_ID 一条按时间有序的序列」。本类用
// ConcurrentHashMap<String, ConcurrentSkipListMap> 让每个g一个**并发安全的有序桶**：
// append 按时间点写入、queryWindow 给出闭区间全部点(O(log n + k))，全部无锁即可并发读写。
// 真实平台会把桶落到时序库/按 (sourceId, time) 排序的存储(见主文档 3.7)，内存版保留同样心智。
import java.util.ArrayList;
import java.util.List;
import java.util.NavigableMap;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentSkipListMap;

public final class JobHistoryStore {
    private final ConcurrentHashMap<String, ConcurrentSkipListMap<Long, JobRecord>> byVin =
            new ConcurrentHashMap<>();

    /** 追加一个点：同秒重复点被覆盖(去重)。 */
    public void append(JobRecord p) {
        byVin.computeIfAbsent(p.sourceId(), k -> new ConcurrentSkipListMap<>())
                .put(p.atEpochSec(), p);
    }

    /** 时间窗查询：闭区间 [fromSec, toSec] 内按时间升序的全部点。 */
    public List<JobRecord> queryWindow(String sourceId, long fromSec, long toSec) {
        NavigableMap<Long, JobRecord> bucket = byVin.get(sourceId);
        if (bucket == null) {
            return List.of();
        }
        return new ArrayList<>(bucket.subMap(fromSec, true, toSec, true).values());
    }

    /** 最新一点：判断数据源此刻位置/是否刚有上报。 */
    public JobRecord latest(String sourceId) {
        NavigableMap<Long, JobRecord> bucket = byVin.get(sourceId);
        if (bucket == null || bucket.isEmpty()) {
            return null;
        }
        return bucket.lastEntry().getValue();
    }

    public int totalPoints() {
        return byVin.values().stream().mapToInt(NavigableMap::size).sum();
    }
}
