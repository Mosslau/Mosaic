// languages/java/ph23-lakehouse-orchestration/examples/ex08-quality-lineage-cost/TableCommitGate.java —— 门禁即发布前置条件：未全过则拒绝提交（fail-closed），表停在上一快照
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex08 *.java && java -cp /tmp/ph23-ex08 QualityLineageCostDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：9/9 PASS）
import java.util.ArrayList;
import java.util.List;

/**
 * 把质量门禁接在**提交之前**：坏数据进表比任务失败贵得多（3.8）。
 *
 * 语义（最小但完整）：
 *   commit(rows) → 先跑 {@link QualityGate#check}；任何一类 FAIL 就**拒绝**，当前快照 id 与行数据保持不变；
 *   全部通过才提交：快照 id +1，行数据整体替换，并记录一次成功提交。
 *   commit 永远不可变地返回 {@link CommitOutcome}（含门禁结果与前后快照 id），调用方不需要看日志就知道发生了什么。
 *
 * 为什么是 fail-closed 而不是「告警后继续」：告警是异步的（人可能没看到），而坏数据一旦提交，
 * 下游所有任务都会基于它产出错误结果，修复成本随时间指数上升——所以必须在**最早的、代价最低的位置**拦下。
 * 这与 ph22 的「配额拒绝而非排队」是同一种工程直觉。
 */
public final class TableCommitGate {

    /** 一次提交尝试的结果：操作名、门禁明细、提交前后快照 id、是否真的提交了。 */
    public record CommitOutcome(String operation, List<QualityGate.GateResult> gateResults,
                                long snapshotBefore, long snapshotAfter, boolean committed,
                                int rowCount) {
        public CommitOutcome {
            gateResults = List.copyOf(gateResults);
        }

        /** 是否所有门禁都通过（与 committed 同义，但单独暴露便于断言）。 */
        public boolean allGatePassed() {
            return QualityGate.allPassed(gateResults);
        }
    }

    /** 提交历史（审计用）：只记录**尝试**，包括被拒绝的那些。 */
    public record CommitRecord(long snapshotId, String operation, boolean committed, List<String> failedChecks) {
        public CommitRecord {
            failedChecks = List.copyOf(failedChecks);
        }
    }

    private final long expectedRowCount;
    private final long nowMillis;
    private long currentSnapshotId;
    private List<QualityGate.Row> currentRows;
    private int commits;
    private int rejections;
    private final List<CommitRecord> history = new ArrayList<>();

    public TableCommitGate(long initialSnapshotId, List<QualityGate.Row> initialRows,
                           long expectedRowCount, long nowMillis) {
        this.currentSnapshotId = initialSnapshotId;
        this.currentRows = List.copyOf(initialRows);
        this.expectedRowCount = expectedRowCount;
        this.nowMillis = nowMillis;
    }

    /**
     * 尝试提交一批数据：门禁未全过 → 拒绝（快照与数据都不动）；全过 → 快照 +1 并整体替换数据。
     * 时钟与行数基线在构造时固定，所以同一批数据的判定每次完全一致（可复现）。
     */
    public CommitOutcome commit(String operation, List<QualityGate.Row> rows) {
        List<QualityGate.GateResult> results = QualityGate.check(rows, expectedRowCount, nowMillis);
        List<String> failed = QualityGate.failedNames(results);
        long before = currentSnapshotId;
        boolean committed = failed.isEmpty();
        if (committed) {
            currentSnapshotId = before + 1;
            currentRows = List.copyOf(rows);
            commits++;
        } else {
            rejections++;
        }
        history.add(new CommitRecord(currentSnapshotId, operation, committed, failed));
        return new CommitOutcome(operation, results, before, currentSnapshotId, committed, rows.size());
    }

    public long currentSnapshotId() {
        return currentSnapshotId;
    }

    public List<QualityGate.Row> currentRows() {
        return List.copyOf(currentRows);
    }

    public int commits() {
        return commits;
    }

    public int rejections() {
        return rejections;
    }

    public List<CommitRecord> history() {
        return List.copyOf(history);
    }

    /** 门禁通过率 = 成功提交 / 总尝试；没有尝试时定义为 0（不出现 NaN）。 */
    public double gatePassRate() {
        int attempts = commits + rejections;
        return attempts == 0 ? 0.0 : commits * 100.0 / attempts;
    }

    /** 提交历史一屏：`#snapshot operation committed failed=[...]`。 */
    public String renderHistory() {
        StringBuilder sb = new StringBuilder();
        for (CommitRecord record : history) {
            if (sb.length() > 0) {
                sb.append('\n');
            }
            sb.append("#").append(record.snapshotId()).append(' ').append(record.operation())
                    .append(record.committed() ? " COMMITTED" : " REJECTED")
                    .append(" failed=").append(record.failedChecks());
        }
        return sb.toString();
    }
}
