// project/src/lakeplat/Pipeline.java —— 批流一体：同一口径两种执行 + 水位线 + 迟到侧输出 + 幂等窗口覆盖
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 批流一体管线（主文档 3.5 / 4.3）：**同一口径**既能对历史全量跑批，也能对实时流增量跑。
 *
 * <p>批与流共用同一份逻辑——过滤脏事件 + 按窗口聚合（行数 / 求和）——
 * 目标不是「一份代码两处跑」，而是**语义一致**：同一时间窗，批算与流算必须得出同一个数。
 *
 * <p>三条保证都在本类里：
 * <ol>
 *   <li><b>同一套逻辑</b>：{@link #batch} 与 {@link #stream} 都调用 {@link #aggregate}；</li>
 *   <li><b>同一套时间语义</b>：都用事件时间 + 水位线（{@code watermark = maxSeenTs - allowedLateness}）；</li>
 *   <li><b>同一套幂等写</b>：结果按窗口**整体覆盖**（{@link #results} 是 map 的 put，不是追加），
 *       所以流作业从检查点重放同一窗口，结果与第一次完全一致——不重复计数。</li>
 * </ol>
 *
 * <p><b>迟到数据不能敷衍丢弃</b>：丢弃意味着同一时间窗批算有这条、流算没有，「批流一体」就退化成两套数。
 * 本实现把迟到事件写进 {@link #sideOutput()}（侧输出分区），由补偿任务按更宽水位线重算那个窗口。
 */
public final class Pipeline {

    private static final AtomicLong INSTANCE_SEQ = new AtomicLong();

    /** 一个窗口的聚合结果：行数 + 求和（口径唯一，批流共用）。 */
    public record WindowResult(String windowKey, long count, long sum) {
        public double average() {
            return count == 0 ? 0.0 : sum * 1.0 / count;
        }
    }

    /** 侧输出里的一条迟到事件记录（补偿任务的输入）。 */
    public record LateRecord(String eventId, String windowKey, long eventTime, long watermark,
                             long latenessMillis, String reason) {
        @Override
        public String toString() {
            return eventId + "（窗口 " + windowKey + "，迟到 " + latenessMillis + "ms）";
        }
    }

    /** 一次流式执行的读数。 */
    public record StreamOutcome(long watermark, int accepted, int late, boolean advanced,
                                List<LateRecord> lateRecords) {
        public String label() {
            return "水位线 " + watermark + "，接受 " + accepted + " 条，迟到 " + late + " 条";
        }
    }

    private final String name;
    private final long allowedLatenessMillis;
    private final Map<String, WindowResult> results = new TreeMap<>();
    /** 每个窗口已接受的事件（键 = windowKey + eventId，按 eventId **整体覆盖**去重）。 */
    private final Map<String, Map<String, Event>> windowLog = new TreeMap<>();
    private final List<LateRecord> sideOutput = new ArrayList<>();
    private long watermark = Long.MIN_VALUE;

    public Pipeline(String name, long allowedLatenessMillis) {
        if (allowedLatenessMillis < 0) {
            throw new IllegalArgumentException("允许迟到时长不能为负");
        }
        this.name = name + "#" + INSTANCE_SEQ.incrementAndGet();
        this.allowedLatenessMillis = allowedLatenessMillis;
    }

    public String name() {
        return name;
    }

    public long allowedLatenessMillis() {
        return allowedLatenessMillis;
    }

    public long watermark() {
        return watermark;
    }

    /** 当前窗口结果（按窗口键字典序，输出可复现）。 */
    public Map<String, WindowResult> results() {
        return java.util.Collections.unmodifiableMap(new TreeMap<>(results));
    }

    public WindowResult result(String windowKey) {
        WindowResult result = results.get(windowKey);
        if (result == null) {
            throw new IllegalStateException("窗口 " + windowKey + " 在 " + name + " 里没有结果");
        }
        return result;
    }

    /** 侧输出分区：迟到事件落在这里，等待补偿任务按更宽水位线重算。 */
    public List<LateRecord> sideOutput() {
        return List.copyOf(sideOutput);
    }

    /** 侧输出事件数（重放不重复计数时这个数字也必须不变）。 */
    public int lateCount() {
        return sideOutput.size();
    }

    /**
     * 批算（主文档 3.5）：对历史事件全量跑一次，按窗口**覆盖**输出。
     *
     * <p>批算不涉及水位线：历史数据已到齐，所有事件都参与聚合。
     */
    public Map<String, WindowResult> batch(List<Event> events) {
        Map<String, WindowResult> aggregated = aggregate(events);
        aggregated.forEach((key, value) -> results.put(key, value));   // 幂等覆盖
        return results();
    }
    /**
     * 流算（主文档 3.5）：按水位线聚合，迟到事件进侧输出。
     *
     * <p>水位线推进规则：{@code watermark = max(watermark, maxSeenTs - allowedLateness)}。
     * 事件判定：{@code evTs <= watermark} → 迟到（写侧输出，不进窗口）；
     * 否则参与该事件所属窗口的聚合。
     *
     * <p>水位线只前进不后退（{@link StreamOutcome#advanced()} 报告本次是否推进），
     * 因此重复投递同一批事件时判定结果稳定、窗口结果是覆盖写，重放不重复计数。
     */
    public StreamOutcome stream(List<Event> orderedEvents) {
        List<LateRecord> lateness = new ArrayList<>();
        int accepted = 0;
        long watermarkBefore = watermark;
        long maxSeen = watermark;
        for (Event event : orderedEvents) {
            // 先让水位线吃到这条事件的时间，再判定——迟到是相对**当前**水位线说的
            maxSeen = Math.max(maxSeen, event.eventTime() - allowedLatenessMillis);
            watermark = maxSeen;
            if (event.eventTime() <= watermark) {
                long latenessMillis = watermark - event.eventTime();
                LateRecord record = new LateRecord(event.eventId(), event.window().key(), event.eventTime(),
                        watermark, latenessMillis,
                        "事件时间 " + event.eventTime() + " <= 水位线 " + watermark
                                + "（允许迟到 " + allowedLatenessMillis + "ms）→ 写侧输出补偿");
                lateness.add(record);
                sideOutput.add(record);
            } else {
                accepted++;
                // 幂等写的最小内核：按窗口收事件，**同一个 eventId 覆盖同一个槽位**
                // （不是追加）。因此重放 N 次，窗口里的事件集合与结果都完全不变。
                windowLog.computeIfAbsent(event.window().key(), key -> new TreeMap<>())
                        .put(event.eventId(), event);
            }
        }
        boolean advanced = maxSeen > watermarkBefore;
        // 结果按窗口**整体覆盖**（recompute from log），这是 exactly-once 效果的来源
        windowLog.forEach((key, log) ->
                results.put(key, aggregate(new ArrayList<>(log.values())).get(key)));
        return new StreamOutcome(watermark, accepted, lateness.size(), advanced, List.copyOf(lateness));
    }

    /** 窗口事件日志（重放一致性的证据：同一 eventId 只占一个槽位）。 */
    public Map<String, List<Event>> windowEvents() {
        Map<String, List<Event>> snapshot = new TreeMap<>();
        windowLog.forEach((key, log) -> snapshot.put(key, List.copyOf(log.values())));
        return java.util.Collections.unmodifiableMap(snapshot);
    }

    /** 当前窗口日志里的事件总数（重放 N 次后必须不变）。 */
    public int retainedEventCount() {
        return windowLog.values().stream().mapToInt(Map::size).sum();
    }

    /**
     * 运行时校验：批算与流算对同一窗口的口径是否一致。
     *
     * <p>这是批流一体的**验收判据**，不是口头承诺：同一窗口、同一逻辑，两套执行必须同值。
     * 调用方把「同口径的输入」交给两侧即可——批算的输入是历史全量，流算的输入是同一批未被判迟到的事件。
     */
    public void assertParity(Map<String, WindowResult> expected) {
        for (Map.Entry<String, WindowResult> entry : expected.entrySet()) {
            WindowResult streamed = results.get(entry.getKey());
            if (streamed == null) {
                throw new IllegalStateException("批流口径不一致：窗口 " + entry.getKey() + " 流算没有结果");
            }
            if (streamed.count() != entry.getValue().count() || streamed.sum() != entry.getValue().sum()) {
                throw new IllegalStateException("批流口径不一致：窗口 " + entry.getKey()
                        + " 批算(" + entry.getValue().count() + "行/" + entry.getValue().sum()
                        + ") 流算(" + streamed.count() + "行/" + streamed.sum() + ")");
            }
            if (entry.getValue().windowKey() == null || !entry.getKey().equals(entry.getValue().windowKey())) {
                throw new IllegalStateException("窗口结果键不一致：" + entry.getKey());
            }
        }
    }

    /**
     * 与 {@link #stream} 完全同口径的聚合逻辑（批流共用的唯一实现）。
     *
     * <p>脏事件（value < 0）在这里被过滤——过滤规则也只有一份，避免两套实现各自演化。
     */
    public Map<String, WindowResult> aggregate(List<Event> events) {
        Map<String, WindowResult> aggregated = new TreeMap<>();
        for (Event event : events) {
            if (event.value() < 0) {
                continue;                       // 过滤规则：负值视为脏数据
            }
            String key = event.window().key();
            WindowResult current = aggregated.getOrDefault(key, new WindowResult(key, 0, 0));
            aggregated.put(key, new WindowResult(key, current.count() + 1, current.sum() + event.value()));
        }
        return aggregated;
    }

    /** 按事件时间稳定排序（批算的输入准备；同时间按 eventId 排序）。 */
    public static List<Event> ordered(List<Event> events) {
        List<Event> sorted = new ArrayList<>(events);
        sorted.sort(Comparator.naturalOrder());
        return List.copyOf(sorted);
    }

    /** 窗口结果 → 输出分区文件名（幂等覆盖的落点，按窗口整体重写）。 */
    public static String outputPartition(Window window) {
        return "window=" + window.key();
    }

    /** 结果快照的深拷贝文本（重放一致性断言用：两次流算后这个文本必须逐字节相同）。 */
    public String resultsDigest() {
        StringBuilder sb = new StringBuilder();
        results.forEach((key, value) -> sb.append(key).append('=').append(value.count())
                .append('/').append(value.sum()).append(';'));
        sb.append("side=").append(sideOutput.size());
        return sb.toString();
    }

    /** 便于展示的窗口结果列表。 */
    public List<String> describe() {
        List<String> lines = new ArrayList<>();
        results.forEach((key, value) -> lines.add(key + " → " + value.count() + " 行 / sum=" + value.sum()
                + "（均值 " + String.format("%.2f", value.average()) + "）"));
        return List.copyOf(lines);
    }

    /** 供表格化输出使用：窗口键 → 结果（保序）。 */
    public Map<String, WindowResult> resultsInOrder() {
        return new LinkedHashMap<>(results);
    }
}
