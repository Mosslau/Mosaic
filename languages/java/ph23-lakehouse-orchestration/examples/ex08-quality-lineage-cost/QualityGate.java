// languages/java/ph23-lakehouse-orchestration/examples/ex08-quality-lineage-cost/QualityGate.java —— 五类质量检查：非空 / 唯一 / 量程 / 行数波动 / 鲜度
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex08 *.java && java -cp /tmp/ph23-ex08 QualityLineageCostDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：9/9 PASS）
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * 质量门禁：`check(rows)` 返回**固定五类**检查结果，每一类都必须能独立拦下对应的坏数据（3.8）。
 *
 * | 检查 | 拦什么 | 判据 |
 * |------|--------|------|
 * | notNull | 关键列缺失 | id / instanceId / eventTime 有 null 或空串 |
 * | unique | 主键重复 | id 出现次数 > 1 |
 * | range | 量程越界 | latencyMs ∉ [0, 3000] |
 * | rowCountDelta | 批次行数暴涨/暴跌 | |本批 - 基线| / 基线 > 容忍比例 |
 * | freshness | 数据太旧 | 时钟 - max(eventTime) > 上限 |
 *
 * 三条纪律写进签名里：
 *   ① **时钟显式传入**（`nowMillis`），不读系统时间——门禁结果必须可复现；
 *   ② **量程边界半开**（`[min,max]` 闭区间，超出即 FAIL），避免「刚好等于上限」这种边界扯皮；
 *   ③ **空批次不是「全过」**：没有数据可检查时，rowCountDelta 与 freshness 都以 FAIL 收场
 *      （fail-closed：宁可挡住一次空跑，也不能让空分区进表）。
 */
public final class QualityGate {

    /** 一条待检查的明细行（示例取 DWD 事件表最关键的几列）。 */
    public record Row(String id, String instanceId, long eventTime, long latencyMs) { }

    /** 单类检查结果：名字 + 是否通过 + 可读细节（细节里带数字，便于值班直接定位）。 */
    public record GateResult(String name, boolean passed, String detail) { }

    /** 五类检查的规范顺序：固定渲染顺序 → 门禁报告可 diff。 */
    public static final List<String> CHECK_NAMES =
            List.of("notNull", "unique", "range", "rowCountDelta", "freshness");

    /** 量程口径：latencyMs ∈ [0, 3000]。 */
    public static final long LATENCY_MIN = 0L;
    public static final long LATENCY_MAX = 3_000L;
    /** 鲜度上限：数据最新事件时间距今不得超过 6 小时。 */
    public static final long FRESHNESS_LIMIT_MILLIS = 6 * 60 * 60 * 1000L;
    /** 行数波动容忍比例：偏离基线 50% 即 FAIL。 */
    public static final double ROW_COUNT_TOLERANCE = 0.5;

    private QualityGate() { }

    /**
     * 跑满五类检查（不短路：即使 notNull 已 FAIL，也把五类结果全算出来——值班一次看到全貌）。
     *
     * @param rows        本批数据
     * @param expectedRowCount 基线行数（上一批或近 7 天均值，由调用方显式给出）
     * @param nowMillis   当前时钟（显式传入，不读系统时间）
     */
    public static List<GateResult> check(List<Row> rows, long expectedRowCount, long nowMillis) {
        List<GateResult> results = new ArrayList<>();

        // ① notNull：关键列缺失
        List<String> nullIds = new ArrayList<>();
        for (Row row : rows) {
            if (isBlank(row.id()) || isBlank(row.instanceId())) {
                nullIds.add(String.valueOf(row.id()));
            }
        }
        results.add(new GateResult("notNull", nullIds.isEmpty(),
                nullIds.isEmpty() ? "关键列 id/instanceId 全部非空（" + rows.size() + " 行）"
                        : "存在空 key 行：" + nullIds));

        // ② unique：主键重复
        Set<String> seen = new HashSet<>();
        Set<String> duplicates = new java.util.TreeSet<>();
        for (Row row : rows) {
            if (!seen.add(row.id())) {
                duplicates.add(String.valueOf(row.id()));
            }
        }
        results.add(new GateResult("unique", duplicates.isEmpty(),
                duplicates.isEmpty() ? "主键 id 唯一（去重后 " + seen.size() + " 行）"
                        : "主键重复：" + duplicates));

        // ③ range：量程越界
        List<String> outOfRange = new ArrayList<>();
        for (Row row : rows) {
            if (row.latencyMs() < LATENCY_MIN || row.latencyMs() > LATENCY_MAX) {
                outOfRange.add(row.id() + "=" + row.latencyMs());
            }
        }
        results.add(new GateResult("range", outOfRange.isEmpty(),
                outOfRange.isEmpty() ? "latencyMs 全部落在 [" + LATENCY_MIN + "," + LATENCY_MAX + "]"
                        : "越界行：" + outOfRange));

        // ④ rowCountDelta：行数波动（基线为 0 或无数据时 fail-closed）
        double delta = expectedRowCount == 0 ? (rows.isEmpty() ? 0.0 : Double.POSITIVE_INFINITY)
                : Math.abs(rows.size() - expectedRowCount) / (double) expectedRowCount;
        boolean rowCountOk = expectedRowCount > 0 && delta <= ROW_COUNT_TOLERANCE;
        results.add(new GateResult("rowCountDelta", rowCountOk,
                "本批 " + rows.size() + " 行 vs 基线 " + expectedRowCount + " 行，偏离 "
                        + (Double.isInfinite(delta) ? "∞" : String.format("%.1f%%", delta * 100))
                        + "（容忍 " + String.format("%.0f%%", ROW_COUNT_TOLERANCE * 100) + "）"));

        // ⑤ freshness：数据太旧（空批次没有「最新事件时间」，同样 fail-closed）
        long maxEventTime = Long.MIN_VALUE;
        for (Row row : rows) {
            maxEventTime = Math.max(maxEventTime, row.eventTime());
        }
        boolean fresh = maxEventTime != Long.MIN_VALUE && nowMillis - maxEventTime <= FRESHNESS_LIMIT_MILLIS;
        results.add(new GateResult("freshness", fresh,
                maxEventTime == Long.MIN_VALUE ? "空批次没有事件时间，判 FAIL（fail-closed）"
                        : "最新事件距今 " + (nowMillis - maxEventTime) + "ms（上限 " + FRESHNESS_LIMIT_MILLIS + "ms）"));

        return results;
    }

    /** 全过才算通过——这是 TableCommitGate 唯一的放行条件（门禁即发布前置条件）。 */
    public static boolean allPassed(List<GateResult> results) {
        return results.stream().allMatch(GateResult::passed);
    }

    /** 未通过的检查名（一屏/告警只关心这些）。 */
    public static List<String> failedNames(List<GateResult> results) {
        List<String> failed = new ArrayList<>();
        for (GateResult result : results) {
            if (!result.passed()) {
                failed.add(result.name());
            }
        }
        return failed;
    }

    /** 门禁报告：`name=PASS/FAIL(detail)` 按规范顺序。 */
    public static String render(List<GateResult> results) {
        StringBuilder sb = new StringBuilder();
        for (GateResult result : results) {
            if (sb.length() > 0) {
                sb.append(" | ");
            }
            sb.append(result.name()).append('=').append(result.passed() ? "PASS" : "FAIL")
                    .append('(').append(result.detail()).append(')');
        }
        return sb.toString();
    }

    /** 便于断言「某一类检查单独拦下了坏数据」。 */
    public static boolean failed(List<GateResult> results, String name) {
        return results.stream().anyMatch(result -> result.name().equals(name) && !result.passed());
    }

    /** 便于断言「除某一类之外全部通过」。 */
    public static boolean onlyFailed(List<GateResult> results, String name) {
        List<String> failed = failedNames(results);
        return failed.size() == 1 && failed.get(0).equals(name);
    }

    /** 日界线用的时间字符串（确定性自造，不读系统时钟）。 */
    public static long millis(String isoInstant) {
        return Instant.parse(isoInstant).toEpochMilli();
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
