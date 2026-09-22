// exercises/sol-01-source-report/ReportApi.java —— 数据源数据上报 API(参考实现)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-sol *.java
//
// 题目要求(roadmap §21 练习「数据源数据上报 API」)：
//   - 实现数据源上报 API 的判定核心：非法帧拒绝、越界帧拒绝、每个数据源乱序去重；
//   - 线程安全：多路网关并发上报同一 SOURCE_ID 不丢帧、不乱序覆写；
//   - 可查询：能回答某数据源当前状态、全平台处理统计。
// 参考实现用 ConcurrentHashMap + compute 把「读旧 seq→比较→写新」做成原子段(与 examples/ex03 同源)。
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.LongAdder;

public final class ReportApi {
    public enum Verdict { OK, REJECT_INVALID_VIN, REJECT_RANGE, DUPLICATE }

    private final ConcurrentHashMap<String, DataReport> latestByVin = new ConcurrentHashMap<>();
    private final LongAdder okCount = new LongAdder();
    private final LongAdder rejectCount = new LongAdder();

    /** 处理一条上报。网关层(Netty/ex02)每收到一帧调用一次。 */
    public Verdict handle(DataReport report) {
        if (!report.vinValid()) {
            rejectCount.increment();
            return Verdict.REJECT_INVALID_VIN;
        }
        if (!report.rangeValid()) {
            rejectCount.increment();
            return Verdict.REJECT_RANGE;
        }
        boolean[] accepted = {false};
        latestByVin.compute(report.sourceId(), (sourceId, cur) -> {
            if (cur == null || report.seq() > cur.seq()) {   // 首帧或更新帧
                accepted[0] = true;
                return report;
            }
            return cur;                                       // 乱序/重复：保留旧值
        });
        if (accepted[0]) {
            okCount.increment();
            return Verdict.OK;
        }
        rejectCount.increment();
        return Verdict.DUPLICATE;
    }

    public DataReport latest(String sourceId)          { return latestByVin.get(sourceId); }
    public long okCount()                            { return okCount.sum(); }
    public long rejectCount()                        { return rejectCount.sum(); }
    public List<String> knownVins() {
        return latestByVin.keySet().stream().sorted().toList();
    }
}
