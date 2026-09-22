// project/src/lakeplat/OpsConsole.java —— 运维一屏：表/快照/成本/编排四块 + Prometheus 文本（同源一致）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.List;

/**
 * 运维一屏（主文档 3.8）：湖仓值班只需要回答四个问题——
 * <b>表建得对不对、数据是哪个快照、要扫多少字节、任务堵在哪里</b>。
 *
 * <p>本类是各域的**只读聚合器**（不拥有任何数据）：{@link #snapshot()} 在调用时读取
 * {@link LakePlatform} 的当前状态，因此「人看的一屏」和「机器抓的 Prometheus 文本」必然一致——
 * 「大屏和告警数字对不上」这类事故从结构上被排除。
 *
 * <p>指标名统一用 {@code lake_} 前缀，标签用 {@code table}/{@code layer}/{@code state}，
 * 直接挂到 HTTP {@code /metrics} 即可被 Prometheus 抓取（部署与告警规则属运维内容）。
 */
public final class OpsConsole {

    private final LakePlatform platform;

    public OpsConsole(LakePlatform platform) {
        this.platform = platform;
    }

    /** 四块聚合读数（字段全部来自各域当前状态，无缓存、无副本）。 */
    public record OpsView(int tables, int partitions, int files, long storageBytes,
                          long scanBytes, long scanFullBytes, double scanSavedRatio,
                          int smallFilePartitions, int compactionPlannedPartitions,
                          double compactionReadSavedRatio,
                          long currentSnapshotId, int snapshots, long commitAttempts,
                          long incrementalPartitions, long timeTravelRows,
                          String gateLabel, long gateFailedChecks,
                          int dagNodes, int dagSucceeded, int dagFailed, int dagBlocked,
                          long backfillApplied, long backfillSkipped, int reasonLogs,
                          int lineageColumns, int odsSourceColumns,
                          List<CostReport.TableCost> tableCosts) {
    }

    /** 四块聚合快照（每次调用重新读取，天然与各域同步）。 */
    public OpsView snapshot() {
        List<CostReport.TableCost> costs = platform.costs().tables();
        return new OpsView(
                platform.model().tableCount(), platform.partitionCount(), platform.fileCount(),
                platform.storageBytes(),
                platform.lastScanBytes(), platform.lastScanFullBytes(), platform.lastScanSavedRatio(),
                platform.smallFilePartitions(), platform.compactionPlans().size(),
                platform.compactionReadSavedRatio(),
                platform.currentSnapshotId(), platform.snapshotCount(), platform.commitAttempts(),
                platform.lastIncrementalPartitions(), platform.lastTimeTravelRows(),
                platform.lastGateLabel(), platform.lastGateFailedChecks(),
                platform.dagNodeCount(), platform.dagSucceeded(), platform.dagFailed(), platform.dagBlocked(),
                platform.backfillApplied(), platform.backfillSkipped(), platform.reasonLogCount(),
                platform.lineageNodeCount(), platform.odsSourceColumnCount(),
                costs);
    }

    /** 人看的一屏：四块 + 明细。 */
    public void print() {
        OpsView v = snapshot();
        System.out.println("+---------------------------- 湖仓与编排运维一屏 ----------------------------+");
        System.out.printf("  [表] %d 张表 / %d 个分区 / %d 个文件 / 存储 %dB%n",
                v.tables(), v.partitions(), v.files(), v.storageBytes());
        System.out.printf("  [快照] current=#%d / 共 %d 个快照 / CAS 提交尝试 %d 次 | 最近增量读 %d 个分区 / 时间旅行 %d 行%n",
                v.currentSnapshotId(), v.snapshots(), v.commitAttempts(),
                v.incrementalPartitions(), v.timeTravelRows());
        System.out.printf("  [成本] 扫描 %d/%d 字节（裁剪 %.1f%%）| 小文件分区 %d 个 | compaction 方案 %d 个（读收益 %.1f%%）%n",
                v.scanBytes(), v.scanFullBytes(), v.scanSavedRatio() * 100,
                v.smallFilePartitions(), v.compactionPlannedPartitions(), v.compactionReadSavedRatio() * 100);
        System.out.printf("  [编排] DAG %d 节点：成功 %d / 失败 %d / 阻塞 %d | 回填 %d 个分区（跳过 %d）/ 留痕 %d 条%n",
                v.dagNodes(), v.dagSucceeded(), v.dagFailed(), v.dagBlocked(),
                v.backfillApplied(), v.backfillSkipped(), v.reasonLogs());
        System.out.printf("  [治理] 门禁 %s | 列级血缘 %d 列（ODS 源列 %d）%n",
                v.gateLabel(), v.lineageColumns(), v.odsSourceColumns());
        for (CostReport.TableCost cost : v.tableCosts()) {
            System.out.println("        " + CostReport.line(cost));
        }
        System.out.println("+---------------------------------------------------------------------------+");
    }

    /**
     * Prometheus 文本指标（主文档 3.8）：与 {@link #snapshot()} 共用同一份读数。
     *
     * <p>指标名全部 {@code lake_} 前缀；标签用 {@code table}/{@code layer}/{@code state}。
     */
    public String prometheusText() {
        OpsView v = snapshot();
        StringBuilder sb = new StringBuilder();
        sb.append("# 表建得对不对 / 数据是哪个快照 / 要扫多少字节 / 任务堵在哪里\n");
        sb.append("lake_tables_total ").append(v.tables()).append('\n');
        sb.append("lake_partitions_total ").append(v.partitions()).append('\n');
        sb.append("lake_files_total ").append(v.files()).append('\n');
        sb.append("lake_storage_bytes ").append(v.storageBytes()).append('\n');
        sb.append("lake_snapshot_current_id ").append(v.currentSnapshotId()).append('\n');
        sb.append("lake_snapshots_total ").append(v.snapshots()).append('\n');
        sb.append("lake_commit_attempts_total ").append(v.commitAttempts()).append('\n');
        sb.append("lake_incremental_partitions ").append(v.incrementalPartitions()).append('\n');
        sb.append("lake_time_travel_rows ").append(v.timeTravelRows()).append('\n');
        sb.append("lake_scan_bytes ").append(v.scanBytes()).append('\n');
        sb.append("lake_scan_bytes_full ").append(v.scanFullBytes()).append('\n');
        sb.append("lake_scan_saved_ratio ").append(round3(v.scanSavedRatio())).append('\n');
        sb.append("lake_small_file_partitions ").append(v.smallFilePartitions()).append('\n');
        sb.append("lake_compaction_plans ").append(v.compactionPlannedPartitions()).append('\n');
        sb.append("lake_compaction_read_saved_ratio ").append(round3(v.compactionReadSavedRatio())).append('\n');
        sb.append("lake_quality_gate_failed_checks ").append(v.gateFailedChecks()).append('\n');
        sb.append("lake_dag_nodes ").append(v.dagNodes()).append('\n');
        sb.append("lake_dag_tasks{state=\"succeeded\"} ").append(v.dagSucceeded()).append('\n');
        sb.append("lake_dag_tasks{state=\"failed\"} ").append(v.dagFailed()).append('\n');
        sb.append("lake_dag_tasks{state=\"blocked\"} ").append(v.dagBlocked()).append('\n');
        sb.append("lake_backfill_partitions_total{result=\"applied\"} ").append(v.backfillApplied()).append('\n');
        sb.append("lake_backfill_partitions_total{result=\"skipped\"} ").append(v.backfillSkipped()).append('\n');
        sb.append("lake_backfill_reason_logs ").append(v.reasonLogs()).append('\n');
        sb.append("lake_lineage_columns ").append(v.lineageColumns()).append('\n');
        sb.append("lake_lineage_ods_source_columns ").append(v.odsSourceColumns()).append('\n');
        for (CostReport.TableCost cost : v.tableCosts()) {
            sb.append("lake_table_storage_bytes{table=\"").append(cost.table()).append("\",layer=\"")
                    .append(cost.layer()).append("\"} ").append(cost.bytes()).append('\n');
            sb.append("lake_table_files{table=\"").append(cost.table()).append("\",layer=\"")
                    .append(cost.layer()).append("\"} ").append(cost.files()).append('\n');
            sb.append("lake_table_partitions{table=\"").append(cost.table()).append("\",layer=\"")
                    .append(cost.layer()).append("\"} ").append(cost.partitions()).append('\n');
        }
        return sb.toString();
    }

    /** 定点三位小数：避免 double 的尾数噪声破坏「逐字节可复现」。 */
    private static double round3(double value) {
        return Math.round(value * 1000.0) / 1000.0;
    }
}
