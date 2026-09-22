// project/src/lakeplat/QualityGate.java —— 质量门禁：fail-closed（失败就不发布快照）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 质量门禁（主文档 3.8）：非空 / 唯一 / 量程 / 行数波动 / 鲜度五类检查。
 *
 * <p>关键取舍：门禁失败不是「告警后继续」，而是**不发布**（fail-closed）。
 * 告警是异步的（人可能没看到），而坏数据一旦提交，下游所有任务都会基于它产出错误结果，
 * 且修复成本随时间指数上升（下游要全链重算）。所以门禁必须挡在**提交之前**——
 * 与 ph22 的「配额拒绝而非排队」是同一种工程直觉：**在最早的、代价最低的位置拦下错误**。
 */
public final class QualityGate {

    /** 五类门禁检查。 */
    public enum Check {
        NOT_NULL("非空"),
        UNIQUE("唯一"),
        RANGE("量程"),
        ROW_COUNT("行数波动"),
        FRESHNESS("鲜度");

        private final String cnName;

        Check(String cnName) {
            this.cnName = cnName;
        }

        public String cnName() {
            return cnName;
        }
    }

    /** 单条检查结果（失败也带可读原因，值班不需要猜）。 */
    public record GateResult(Check check, boolean passed, String detail) {
        @Override
        public String toString() {
            return (passed ? "PASS " : "FAIL ") + check.cnName() + "：" + detail;
        }
    }

    /** 一次门禁的整体裁决：fail-closed——只要有一条 FAIL 就不放行。 */
    public record Verdict(boolean allowed, List<GateResult> results, String message) {
        public long failedCount() {
            return results.stream().filter(r -> !r.passed()).count();
        }

        public String label() {
            return (allowed ? "放行" : "拒绝") + "（" + failedCount() + "/" + results.size() + " 项失败）";
        }
    }

    /** 门禁输入：一次候选提交的数据读数（行 + 列值 + 唯一键 + 事件时间）。 */
    public record Batch(String table, String partition, List<Row> rows) {
    }

    /** 一行数据的列视图（示例只带门禁需要的列）。 */
    public record Row(long eventId, long instanceId, long latencyMs, long eventTime, String region) {
    }

    /** 门禁策略：五类检查的阈值都在这里显式声明，便于评审。 */
    public record Policy(long minRows, long maxRows, long rowCountTolerancePct,
                         long latencyMin, long latencyMax, long maxLagMillis,
                         String uniqueKeyColumn) {
        public static Policy defaults() {
            return new Policy(1, 1_000_000, 20, 0, 60_000, 6 * 3_600_000L, "eventId");
        }
    }

    private final Policy policy;

    public QualityGate(Policy policy) {
        this.policy = policy;
    }

    public Policy policy() {
        return policy;
    }

    /**
     * 执行五类检查并给出裁决。
     *
     * @param batch            候选提交的数据
     * @param expectedRows     期望行数基准（历史分区行数；用于行数波动检查）
     * @param freshnessAt      数据新鲜度参照点（逻辑时钟；典型是水位线）
     */
    public Verdict check(Batch batch, long expectedRows, long freshnessAt) {
        List<GateResult> results = new ArrayList<>();
        results.add(notNull(batch));
        results.add(unique(batch));
        results.add(range(batch));
        results.add(rowCount(batch, expectedRows));
        results.add(freshness(batch, freshnessAt));
        boolean allowed = results.stream().allMatch(GateResult::passed);
        long failed = results.stream().filter(r -> !r.passed()).count();
        String message = allowed
                ? "五类门禁全部通过，允许提交"
                : "门禁失败 " + failed + " 项 → fail-closed：本次提交被拒，表保持上一个快照";
        return new Verdict(allowed, List.copyOf(results), message);
    }

    private GateResult notNull(Batch batch) {
        long nulls = batch.rows().stream()
                .filter(row -> row.region() == null || row.region().isBlank())
                .count();
        return new GateResult(Check.NOT_NULL, nulls == 0,
                nulls == 0 ? batch.rows().size() + " 行关键列非空"
                        : "发现 " + nulls + " 行关键列为空（列 " + policy.uniqueKeyColumn() + "/region）");
    }

    private GateResult unique(Batch batch) {
        Map<Long, Integer> seen = new LinkedHashMap<>();
        for (Row row : batch.rows()) {
            seen.merge(row.eventId(), 1, Integer::sum);
        }
        List<String> duplicates = new ArrayList<>();
        seen.forEach((id, count) -> {
            if (count > 1) {
                duplicates.add("#" + id + "×" + count);
            }
        });
        return new GateResult(Check.UNIQUE, duplicates.isEmpty(),
                duplicates.isEmpty() ? "主键 " + policy.uniqueKeyColumn() + " 无重复（" + seen.size() + " 个唯一值）"
                        : "主键 " + policy.uniqueKeyColumn() + " 重复：" + duplicates);
    }

    private GateResult range(Batch batch) {
        List<String> violations = new ArrayList<>();
        for (Row row : batch.rows()) {
            if (row.latencyMs() < policy.latencyMin() || row.latencyMs() > policy.latencyMax()) {
                violations.add("event#" + row.eventId() + "=" + row.latencyMs());
            }
        }
        return new GateResult(Check.RANGE, violations.isEmpty(),
                violations.isEmpty() ? "量程 [" + policy.latencyMin() + "," + policy.latencyMax() + "] 内全部通过"
                        : "越界值：" + violations);
    }

    private GateResult rowCount(Batch batch, long expectedRows) {
        if (expectedRows <= 0) {
            return new GateResult(Check.ROW_COUNT, true, "无历史基准，跳过波动检查（本次 " + batch.rows().size() + " 行）");
        }
        double change = Math.abs(batch.rows().size() - expectedRows) * 100.0 / expectedRows;
        boolean passed = change <= policy.rowCountTolerancePct();
        return new GateResult(Check.ROW_COUNT, passed,
                "本次 " + batch.rows().size() + " 行 vs 基准 " + expectedRows + " 行，波动 "
                        + String.format("%.1f", change) + "%（阈值 " + policy.rowCountTolerancePct() + "%）");
    }

    private GateResult freshness(Batch batch, long freshnessAt) {
        if (batch.rows().isEmpty()) {
            return new GateResult(Check.FRESHNESS, false, "空批次没有鲜度可言");
        }
        long maxEventTime = batch.rows().stream().mapToLong(Row::eventTime).max().orElseThrow();
        long lag = freshnessAt - maxEventTime;
        boolean passed = lag <= policy.maxLagMillis();
        return new GateResult(Check.FRESHNESS, passed,
                "最新事件时间 " + maxEventTime + " 距参照点 " + freshnessAt + " 滞后 " + lag
                        + "ms（阈值 " + policy.maxLagMillis() + "ms）");
    }
}
