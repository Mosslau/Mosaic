// languages/java/ph23-lakehouse-orchestration/examples/ex05-batch-stream-unified/Window.java —— 窗口分区：批流共用的「输出分区」身份，也是幂等覆盖的粒度（3.5）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex05 *.java && java -cp /tmp/ph23-ex05 UnifiedPipelineDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）

/**
 * 窗口分区身份 = (key, windowStart, windowEnd)，取**半开区间** [windowStart, windowEnd)。
 *
 * 半开区间不是随手选的：`ts / 60000 * 60000` 这种整除去算窗口，只有在半开区间下才能让
 * 「59999 → 窗口 [0,60000)」「60000 → 窗口 [60000,120000)」都只用一次除法和一次乘法算出来；
 * 闭区间则需要在边界上做特殊判断，是窗口重复计数/漏计数的经典来源。
 *
 * 这个 record 同时是**幂等写**的单位：流式重放与批算都按 (key,window) **整体覆盖**输出，
 * 所以它必须值语义（record 的 equals/hashCode）——覆盖时靠它做 Map 的键（3.5「幂等分区覆盖」）。
 */
public record Window(String key, long windowStart, long windowEnd) implements Comparable<Window> {

    public Window {
        if (key == null || key.isBlank()) {
            throw new IllegalArgumentException("窗口 key 不能为空");
        }
        if (windowStart < 0 || windowEnd <= windowStart) {
            throw new IllegalArgumentException("窗口区间必须满足 0 ≤ start < end：" + windowStart + "~" + windowEnd);
        }
    }

    /**
     * 窗口的**确定性排序**：先按 key，再按 windowStart。
     * 让窗口结果天然落在 TreeMap 里 → 一屏输出与断言可以逐行 diff，
     * 不会因为 HashMap 的遍历顺序抖动而让人误以为「数变了」。
     */
    @Override
    public int compareTo(Window other) {
        int byKey = key.compareTo(other.key);
        return byKey != 0 ? byKey : Long.compare(windowStart, other.windowStart);
    }

    /** 固定长度窗口分配：60_000ms 一窗，半开区间；公式与批、流两侧**完全相同**。 */
    public static Window of(String key, long eventTs, long windowSizeMillis) {
        if (windowSizeMillis <= 0) {
            throw new IllegalArgumentException("窗口长度必须为正：" + windowSizeMillis);
        }
        long start = Math.floorDiv(eventTs, windowSizeMillis) * windowSizeMillis;
        return new Window(key, start, start + windowSizeMillis);
    }

    /** 该窗口是否包含某个事件时间——侧输出补偿时用来判断「这条迟到事件属于哪个窗口」。 */
    public boolean contains(long eventTs) {
        return eventTs >= windowStart && eventTs < windowEnd;
    }

    /** 值语义的字符串：用于稳定输出（Map 遍历顺序在渲染时才排序，不依赖它）。 */
    @Override
    public String toString() {
        return key + "@[" + windowStart + "," + windowEnd + ")";
    }
}
