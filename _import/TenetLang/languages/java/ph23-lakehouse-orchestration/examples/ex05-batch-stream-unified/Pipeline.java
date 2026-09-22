// languages/java/ph23-lakehouse-orchestration/examples/ex05-batch-stream-unified/Pipeline.java —— 同一口径两种执行：批算全量、流算增量水位线 + 迟到侧输出 + 幂等窗口覆盖
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex05 *.java && java -cp /tmp/ph23-ex05 UnifiedPipelineDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

/**
 * 批流一体的最小语义模型：**一份口径（窗口分配 + count/sum 聚合），两种执行**。
 *
 * 批（{@link #batch}）：对历史全量事件跑一遍，按 (key,window) 聚合。有界输入、可随时重跑。
 * 流（{@link #stream}）：对「新到达的事件」按到达顺序处理，维护 `watermark = maxSeenEventTs - allowedLateness`；
 *   `eventTs <= watermark` 的事件判为**迟到**：不参与窗口聚合，而是计入 lateCount 并写入**侧输出**（3.5）。
 *
 * 两条工程纪律决定了这个类为什么长这样：
 *   ① **幂等覆盖**：窗口结果每次都由「截至目前的全部已消费事件」重新计算后**整体覆盖**，不做增量累加。
 *      于是「至少一次投递 + 幂等写 = 效果上的 exactly-once」——重放同一批事件，结果逐项相同、不重复计数。
 *      对照实验见 {@link #applyIncrementally}：如果输出是**追加**语义，同一批事件跑两次就会翻倍。
 *   ② **迟到不丢弃**：迟到事件进侧输出，补偿任务用「已消费事件 ∪ 侧输出」重跑同一口径，结果与批算一致
 *      ——迟到只影响**什么时候**出数，不影响**出什么数**。
 *
 * 确定性来自三个数据结构：窗口 Map 用 TreeMap（按 key + windowStart 排序）、
 * 侧输出用「列表 + HashSet 去重」（首次写入顺序稳定）、已消费事件用 HashSet（重放不重复消费）。
 * 示例不读系统时间：时间语义只由事件里的 eventTs 与显式传入的 allowedLatenessMillis 决定。
 */
public final class Pipeline {

    /** 一个窗口的输出分区：(key,[start,end)) → 聚合值。count/sum 即口径，批与流都只产出这两个数。 */
    public record WindowAgg(long count, double sum) {

        /** 同口径的聚合运算：批、流、补偿三条路径都只用它，所以三者的值必然一致。 */
        public WindowAgg merge(WindowAgg other) {
            return new WindowAgg(count + other.count, sum + other.sum);
        }
    }

    /** 一次处理的完整结果：窗口分区 + 迟到计数 + 侧输出列表 + 水位线快照（不可变）。 */
    public record Result(Map<Window, WindowAgg> windows, int lateCount,
                         List<Event> sideOutput, long lastWatermark, int processedEvents) {

        public Result {
            windows = Map.copyOf(windows);
            sideOutput = List.copyOf(sideOutput);
        }

        public WindowAgg window(String key, long windowStart, long windowEnd) {
            return windows.get(new Window(key, windowStart, windowEnd));
        }
    }

    private final long windowSizeMillis;
    private final long allowedLatenessMillis;
    /** 事件日志：批算与补偿都以「日志」为唯一事实来源（3.2「快照/清单是事实」的同一直觉）。 */
    private final List<Event> log = new ArrayList<>();
    /** 已消费事件：重放时跳过，保证「重放同一批事件」不重复消费（幂等的前提）。 */
    private final Set<Event> consumed = new HashSet<>();
    /**
     * 参与窗口聚合的事件 = 按时到达的事件 ∪ 已被补偿并入的迟到事件。
     * 迟到事件**先**进侧输出、**后**由补偿并入这里——这是「迟到不混进窗口，补偿才并入」的落点。
     */
    private final Set<Event> windowed = new HashSet<>();
    /** 流式处理当前的窗口输出：每次消费后**整体覆盖**。 */
    private Map<Window, WindowAgg> streamOutput = new TreeMap<>();
    /** 侧输出：只保留首次写入，重放不会把它写第二遍。 */
    private final List<Event> sideOutput = new ArrayList<>();
    private final Set<Event> sideOutputSeen = new HashSet<>();
    private int lateCount;
    private long lastWatermark = Long.MIN_VALUE;
    private int processedEvents;

    public Pipeline(long windowSizeMillis, long allowedLatenessMillis) {
        if (windowSizeMillis <= 0) {
            throw new IllegalArgumentException("窗口长度必须为正：" + windowSizeMillis);
        }
        if (allowedLatenessMillis < 0) {
            throw new IllegalArgumentException("允许迟到时长不能为负：" + allowedLatenessMillis);
        }
        this.windowSizeMillis = windowSizeMillis;
        this.allowedLatenessMillis = allowedLatenessMillis;
    }

    /** 纯批算：对给定全量事件按 (key,window) 聚合。无状态、可重复调用、结果逐项确定。 */
    public Map<Window, WindowAgg> batch(List<Event> events) {
        Map<Window, WindowAgg> acc = new TreeMap<>();
        for (Event event : events) {
            acc.merge(Window.of(event.key(), event.eventTs(), windowSizeMillis), new WindowAgg(1, event.value()),
                    WindowAgg::merge);
        }
        return acc;
    }

    /**
     * 流式执行：把事件追加到日志（模拟 broker 的到达顺序），然后逐条按到达顺序处理尚未消费的事件。
     * 每条处理前先算 `watermark = maxSeenEventTs - allowedLateness`（只对已按时到达的事件取最大值）：
     *   - `eventTs <= watermark` → **迟到**：lateCount++ 且写侧输出，**不进**窗口口径；
     *   - 否则 → 按时：进入窗口口径，并成为水位线的候选事件时间。
     * 返回值的窗口 Map 是**整体覆盖**后的最新状态（不是增量）。
     */
    public Result stream(List<Event> arrivals) {
        log.addAll(arrivals);
        for (Event event : log) {
            if (consumed.contains(event) || windowed.contains(event)) {
                continue;   // 已消费（按时）或已被补偿并入的事件不重复处理
            }
            processedEvents++;
            long watermark = maxSeenEventTs() - allowedLatenessMillis;
            if (event.eventTs() <= watermark) {
                // 迟到：只记数与写侧输出，**不进** consumed/windowed —— 等补偿任务把它并入口径
                lateCount++;
                if (sideOutputSeen.add(event)) {
                    sideOutput.add(event);
                }
            } else {
                consumed.add(event);
                windowed.add(event);
            }
        }
        lastWatermark = maxSeenEventTs() - allowedLatenessMillis;
        streamOutput = recomputeWindows(windowed);
        return snapshot();
    }

    /**
     * 重放：对同一份日志再走一次。已消费事件不会被再次消费，窗口由已消费事件**整体覆盖**重算
     * —— 结果与第一次逐项相同，迟到计数不增长（断言 E）。
     */
    public Result replay() {
        return overwrite(recomputeWindows(windowed));
    }

    /**
     * 补偿（侧输出回灌）：把侧输出里的迟到事件当作**新的批输入**并入日志，再跑一次同一口径。
     * 关键点：补偿是「用同一份口径把这个窗口**重算一遍**」，不是「把迟到值加到旧结果上」——
     * 所以这里不进水位线判断（否则迟到事件在补偿里还会被判一次迟到），也不重复计入 lateCount。
     * 因为写是整体覆盖，补偿后的窗口结果与「批算(已消费事件 ∪ 迟到事件)」逐项相同（断言 D）。
     */
    public Result compensate() {
        for (Event event : sideOutput) {
            if (windowed.add(event)) {   // 第一次补偿才并入；重复补偿是幂等空操作
                log.add(event);
            }
        }
        return overwrite(recomputeWindows(windowed));
    }

    /** 对照实验：**追加**语义下把同一批事件再聚合一次——计数直接翻倍。这就是幂等覆盖存在的理由。 */
    public static Map<Window, WindowAgg> applyIncrementally(Map<Window, WindowAgg> base, List<Event> events,
                                                            long windowSizeMillis) {
        Map<Window, WindowAgg> next = new TreeMap<>(base);
        for (Event event : events) {
            next.merge(Window.of(event.key(), event.eventTs(), windowSizeMillis), new WindowAgg(1, event.value()),
                    WindowAgg::merge);
        }
        return next;
    }

    /** 当前结果快照（防御性拷贝由 Result 的紧凑构造器完成）。 */
    public Result snapshot() {
        return new Result(streamOutput, lateCount, sideOutput, lastWatermark, processedEvents);
    }

    public long windowSizeMillis() {
        return windowSizeMillis;
    }

    public long allowedLatenessMillis() {
        return allowedLatenessMillis;
    }

    /** 事件日志（自造数据，不读外部文件）。 */
    public List<Event> log() {
        return List.copyOf(log);
    }

    public List<Event> sideOutput() {
        return List.copyOf(sideOutput);
    }

    public int lateCount() {
        return lateCount;
    }

    public long lastWatermark() {
        return lastWatermark;
    }

    // ---------- 内部：口径的唯一实现 ----------

    /** 口径的唯一实现：给定事件集合 → 按 (key,window) 聚合。批、流、补偿三条路径都调用它。 */
    private Map<Window, WindowAgg> recomputeWindows(Iterable<Event> events) {
        Map<Window, WindowAgg> next = new TreeMap<>();
        int n = 0;
        for (Event event : events) {
            n++;
            next.merge(Window.of(event.key(), event.eventTs(), windowSizeMillis), new WindowAgg(1, event.value()),
                    WindowAgg::merge);
        }
        return next;
    }

    /** 幂等覆盖：把新算出的窗口 Map **整体替换**旧输出，并返回新快照（不做增量累加）。 */
    private Result overwrite(Map<Window, WindowAgg> next) {
        streamOutput = next;
        return snapshot();
    }

    private long maxSeenEventTs() {
        long max = Long.MIN_VALUE;
        for (Event event : consumed) {
            max = Math.max(max, event.eventTs());
        }
        return max == Long.MIN_VALUE ? 0L : max;
    }

    /** 稳定渲染：按 key、再按 windowStart 排序，供一屏/断言逐行 diff。 */
    public static String render(Map<Window, WindowAgg> windows) {
        StringBuilder sb = new StringBuilder();
        for (Map.Entry<Window, WindowAgg> entry : new TreeMap<>(windows).entrySet()) {
            if (sb.length() > 0) {
                sb.append(" | ");
            }
            sb.append(entry.getKey()).append(" count=").append(entry.getValue().count())
                    .append(" sum=").append(entry.getValue().sum());
        }
        return sb.toString();
    }

    /** 供测试构造「同口径」的窗口键，避免断言代码自己重复一遍取整公式。 */
    public Window windowOf(String key, long eventTs) {
        return Window.of(key, eventTs, windowSizeMillis);
    }

    /** 调试/一屏输出：事件按 (eventTs, key) 排序后的可读形式（顺序稳定，可 diff）。 */
    public static List<String> renderEvents(List<Event> events) {
        List<Event> sorted = new ArrayList<>(events);
        sorted.sort((x, y) -> x.eventTs() != y.eventTs()
                ? Long.compare(x.eventTs(), y.eventTs())
                : x.key().compareTo(y.key()));
        List<String> out = new ArrayList<>();
        for (Event event : sorted) {
            out.add(event.key() + "@" + event.eventTs() + "=" + event.value());
        }
        return out;
    }
}
