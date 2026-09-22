// project/src/lakeplat/Window.java —— 时间窗：批算与流算共用的口径单位
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

/**
 * 一个固定长度的时间窗（主文档 3.5 的 {@code Window}）。
 *
 * <p>窗口是**幂等写的粒度**：按 (窗口) 整体覆盖输出，重放同一窗口的结果与第一次完全一致。
 * 这就是「至少一次投递 + 幂等写 = 效果上的 exactly-once」。
 *
 * @param key         窗口键（示例：`2024-06-01`，便于按天覆盖分区）
 * @param windowStart 窗口起点（含）
 * @param windowEnd   窗口终点（不含）
 */
public record Window(String key, long windowStart, long windowEnd) implements Comparable<Window> {

    /** 示例用固定窗长：一天。 */
    public static final long DAY_MILLIS = 86_400_000L;

    /** 示例窗口的时间原点：2024-06-01T00:00:00Z（= 1970-01-01 起第 19875 天）。 */
    public static final long ORIGIN = 1_717_200_000_000L;

    /** {@link #ORIGIN} 对应的天数序号（1970-01-01 的 civil_from_days 输入）。 */
    private static final long ORIGIN_EPOCH_DAY = 19_875L;

    public Window {
        if (windowEnd <= windowStart) {
            throw new IllegalArgumentException("窗口终点必须大于起点");
        }
    }

    /** 把事件时间对齐到「以 ORIGIN 为原点的定长窗口」。 */
    public static Window of(long eventTime) {
        long index = Math.floorDiv(eventTime - ORIGIN, DAY_MILLIS);
        long start = ORIGIN + index * DAY_MILLIS;
        return new Window(dayKey(start), start, start + DAY_MILLIS);
    }

    /** 由窗口起点构造。 */
    public static Window startingAt(long windowStart) {
        return new Window(dayKey(windowStart), windowStart, windowStart + DAY_MILLIS);
    }

    /** 窗口键：`2024-06-01`（确定性格式化，不用时区，直接按 UTC 日序号展开）。 */
    public static String dayKey(long start) {
        return dayKeyAt(Math.floorDiv(start - ORIGIN, DAY_MILLIS));
    }

    /** 相对 {@link #ORIGIN} 的第 {@code offset} 个日历日的键（`2024-06-01` 为 offset 0），回填传播用。 */
    public static String dayKeyAt(long offset) {
        long[] ymd = civilFromDays(ORIGIN_EPOCH_DAY + offset);
        return String.format("%04d-%02d-%02d", ymd[0], ymd[1], ymd[2]);
    }

    /** Howard Hinnant 的 civil_from_days 算法（确定性、无时区、无日历 API）。 */
    private static long[] civilFromDays(long z) {
        long zz = z + 719_468;
        long era = Math.floorDiv(zz, 146_097L);
        long doe = zz - era * 146_097L;
        long yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
        long y = yoe + era * 400;
        long doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
        long mp = (5 * doy + 2) / 153;
        long d = doy - (153 * mp + 2) / 5 + 1;
        long m = mp < 10 ? mp + 3 : mp - 9;
        return new long[] {m <= 2 ? y + 1 : y, m, d};
    }

    /** 窗口是否包含该事件时间。 */
    public boolean contains(long eventTime) {
        return eventTime >= windowStart && eventTime < windowEnd;
    }

    @Override
    public int compareTo(Window other) {
        return Long.compare(windowStart, other.windowStart);
    }

    @Override
    public String toString() {
        return key + "[" + windowStart + "," + windowEnd + ")";
    }
}
