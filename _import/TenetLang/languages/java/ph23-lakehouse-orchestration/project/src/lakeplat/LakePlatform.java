// project/src/lakeplat/LakePlatform.java —— 门面：把分层/快照/布局/compaction/批流/编排/回填/治理编成一条闭环
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

/**
 * 最小湖仓与编排平台的门面（主文档第 7 章「阶段项目」）。
 *
 * <p>把八个域编成**一条闭环**：四层建表与口径 → 写入产生快照（原子提交）→ 分区裁剪与成本估算
 * → 小文件检测与 compaction → 批/流同口径执行 → DAG 编排与失败传播 → 幂等回填与下游重算
 * → 质量门禁 + 列级血缘 + 成本一屏。
 *
 * <p>本类**不实现**任何领域逻辑，只做三件事：持有各域的实例、转发调用、把状态投影成只读读数
 * （{@link #costs()} 与 {@link OpsConsole} 共用同一批读数，因此一屏与指标文本不可能互相矛盾）。
 */
public final class LakePlatform {

    private final WarehouseModel model = new WarehouseModel();
    private final Map<String, TableFormat> formats = new LinkedHashMap<>();
    private final Backfill backfill = new Backfill(model);
    private final CostReport costs = new CostReport(model);
    private final PartitionLayout layout;
    private final Compaction compaction;
    private final QualityGate gate = new QualityGate(QualityGate.Policy.defaults());
    private Lineage lineage;
    private OpsConsole opsConsole;
    private Orchestrator orchestrator;
    private Pipeline pipeline;

    // 最近一次操作的读数（一屏与断言的唯一事实来源）
    private long lastScanBytes;
    private long lastScanFullBytes;
    private long lastIncrementalPartitions = -1;
    private long lastTimeTravelRows = -1;
    private Map<String, Compaction.Plan> compactionPlans = Map.of();
    private List<DataFile> compactionApplied = List.of();
    private long commits;
    private String lastGateLabel = "未执行";
    private long lastGateFailedChecks = -1;
    private long backfillApplied;
    private long backfillSkipped;

    public LakePlatform() {
        this(new PartitionLayout("event_date", 4, 128L * 1024L), new Compaction());
    }

    public LakePlatform(PartitionLayout layout, Compaction compaction) {
        this.layout = layout;
        this.compaction = compaction;
    }

    // ---------- 四层建模与口径（3.1） ----------

    /** 建表：登记层、分区键与「分区键相对事件日期的偏移天数」。 */
    public TableRef createTable(String table, Layer layer, String partitionKey, long partitionOffsetDays,
                                Schema schema, long createdTs) {
        TableRef ref = model.registerTable(new TableRef(table, layer), partitionKey, partitionOffsetDays);
        formats.put(ref.table(), new TableFormat(ref, schema, createdTs, partitionKey));
        return ref;
    }

    /** 声明依赖（校验分层方向）。 */
    public void depend(TableRef downstream, TableRef upstream) {
        model.declareDependency(downstream, upstream);
    }

    /** 声明指标口径（只允许 DWS）。 */
    public void declareMetric(String metric, TableRef owner) {
        model.declareMetric(metric, owner);
    }

    public WarehouseModel model() {
        return model;
    }

    public TableFormat table(TableRef ref) {
        TableFormat format = formats.get(model.require(ref).table());
        if (format == null) {
            throw new IllegalStateException("表 " + ref.table() + " 尚未建表");
        }
        return format;
    }

    // ---------- 快照与提交（3.2） ----------

    /** CAS 提交（失败不改变任何状态，调用方可重读重试）。 */
    public TableFormat.CommitResult commit(TableRef table, long expectedParentId, long tsMillis,
                                           String operation, Schema schema,
                                           Map<String, List<DataFile>> manifest) {
        TableFormat.CommitResult result = table(table).commit(expectedParentId, tsMillis, operation, schema, manifest);
        if (result.accepted()) {
            commits++;
        }
        return result;
    }

    /** 便捷提交（内部重读当前指针）。 */
    public TableFormat.CommitResult commitWithRetry(TableRef table, long tsMillis, String operation,
                                                    Schema schema, Map<String, List<DataFile>> manifest) {
        TableFormat.CommitResult result = table(table).commitWithRetry(tsMillis, operation, schema, manifest);
        commits++;
        return result;
    }

    /** 时间旅行：读出历史快照并记录总行数（断言与一屏用）。 */
    public Snapshot timeTravel(TableRef table, long tsMillis) {
        Snapshot snapshot = table(table).timeTravel(tsMillis);
        lastTimeTravelRows = snapshot.totalRows();
        return snapshot;
    }

    /** 增量读：返回自 {@code sinceId} 以来清单发生变化的分区，并记录读数。 */
    public Set<String> incremental(TableRef table, long sinceId) {
        TableFormat format = table(table);
        Set<String> changed = format.incremental(format.snapshot(sinceId), format.current());
        lastIncrementalPartitions = changed.size();
        return changed;
    }

    public long lastTimeTravelRows() {
        return lastTimeTravelRows;
    }

    public long lastIncrementalPartitions() {
        return lastIncrementalPartitions;
    }

    public long commitAttempts() {
        return commits;
    }

    public long currentSnapshotId() {
        return formats.isEmpty() ? 0 : firstFormat().current().snapshotId();
    }

    public int snapshotCount() {
        return firstFormat().history().size();
    }

    private TableFormat firstFormat() {
        return formats.values().iterator().next();
    }

    // ---------- 分区布局与成本（3.3） ----------

    /** 分区裁剪扫描：记录裁剪前后的字节数（成本一屏的基础）。 */
    public PartitionLayout.ScanCost scan(TableRef table, Set<String> partitions) {
        PartitionLayout.ScanCost cost = layout.scan(table(table).current().files(), partitions);
        lastScanBytes = cost.bytes();
        lastScanFullBytes = cost.fullBytes();
        return cost;
    }

    public long lastScanBytes() {
        return lastScanBytes;
    }

    public long lastScanFullBytes() {
        return lastScanFullBytes;
    }

    public double lastScanSavedRatio() {
        return lastScanFullBytes == 0 ? 0.0 : 1.0 - lastScanBytes * 1.0 / lastScanFullBytes;
    }

    public PartitionLayout layout() {
        return layout;
    }

    // ---------- 小文件治理（3.4） ----------

    /** 规划 compaction：只对「文件多且平均小」的分区出手，并记录方案。 */
    public Map<String, Compaction.Plan> planCompaction(TableRef table) {
        compactionPlans = compaction.planTable(layout, table(table).current().files());
        return compactionPlans;
    }

    /**
     * 幂等 apply：按方案重建分区文件并产生新快照（合并是一次重写，所以会推进快照链）。
     *
     * <p>重复 apply 同一分区得到同样的文件集合，因此清单不变、不会产生额外快照。
     */
    public List<DataFile> applyCompaction(TableRef table, long tsMillis) {
        TableFormat format = table(table);
        if (compactionPlans.isEmpty()) {
            return List.of();
        }
        Map<String, List<DataFile>> manifest = new LinkedHashMap<>(format.current().manifest());
        for (Map.Entry<String, Compaction.Plan> entry : compactionPlans.entrySet()) {
            List<DataFile> before = manifest.getOrDefault(entry.getKey(), List.of());
            List<DataFile> after = compaction.apply(entry.getKey(), before);
            if (after.equals(before)) {
                continue;                       // 已经是目标形态 → 不再产生快照（幂等 apply）
            }
            manifest.put(entry.getKey(), after);
        }
        if (manifest.equals(format.current().manifest())) {
            compactionApplied = List.of();
            return List.of();
        }
        Map<String, List<DataFile>> frozen = new TreeMap<>(manifest);
        format.commitWithRetry(tsMillis, "COMPACT", format.current().schema(), frozen);
        commits++;
        List<DataFile> applied = new ArrayList<>();
        compactionPlans.keySet().forEach(partition -> applied.addAll(frozen.getOrDefault(partition, List.of())));
        compactionApplied = List.copyOf(applied);
        return compactionApplied;
    }

    public Map<String, Compaction.Plan> compactionPlans() {
        return Map.copyOf(compactionPlans);
    }

    /** compaction 后实际落地的新文件（断言幂等性用）。 */
    public List<DataFile> compactionApplied() {
        return compactionApplied;
    }

    public double compactionReadSavedRatio() {
        return compactionPlans.values().stream().mapToDouble(Compaction.Plan::readSavedRatio).average().orElse(0.0);
    }

    public int smallFilePartitions() {
        return layout.detectSmallFilePartitions(table(firstTable()).current().files()).size();
    }

    private TableRef firstTable() {
        return model.tables().get(0);
    }

    // ---------- 批流一体（3.5） ----------

    public Pipeline pipeline() {
        return pipeline;
    }

    /** 装配批流一体管线（同口径、同幂等写）。 */
    public Pipeline pipeline(String name, long allowedLatenessMillis) {
        this.pipeline = new Pipeline(name, allowedLatenessMillis);
        return pipeline;
    }

    // ---------- 编排（3.6） ----------

    public Orchestrator orchestrator() {
        return orchestrator;
    }

    /** 装配 DAG 编排器（并发度 + 确定性执行体）。 */
    public Orchestrator orchestrate(Dag dag, int maxConcurrency, Orchestrator.Executor executor) {
        this.orchestrator = new Orchestrator(dag, maxConcurrency, executor);
        return orchestrator;
    }

    public List<String> topoOrder() {
        return orchestrator == null ? List.of() : orchestrator.dag().topoOrder();
    }

    public int dagNodeCount() {
        return orchestrator == null ? 0 : orchestrator.dag().nodes().size();
    }

    public int dagSucceeded() {
        return orchestrator == null ? 0 : (int) orchestrator.states().values().stream()
                .filter(state -> state == Dag.State.SUCCEEDED).count();
    }

    public int dagFailed() {
        return orchestrator == null ? 0 : orchestrator.failedTasks().size();
    }

    public int dagBlocked() {
        return orchestrator == null ? 0 : orchestrator.blockedTasks().size();
    }

    // ---------- 回填（3.7） ----------

    public Backfill backfill() {
        return backfill;
    }

    public Backfill.RunResult runBackfill(Backfill.Plan plan, long tsMillis) {
        Backfill.RunResult result = backfill.execute(plan, tsMillis);
        backfillApplied += result.applied().size();
        backfillSkipped += result.skipped().size();
        return result;
    }

    public Backfill.RunResult resumeBackfill(Backfill.Plan plan, long tsMillis) {
        Backfill.RunResult result = backfill.resumeAndRun(plan, tsMillis);
        backfillApplied += result.applied().size();
        backfillSkipped += result.skipped().size();
        return result;
    }

    public long backfillApplied() {
        return backfillApplied;
    }

    public long backfillSkipped() {
        return backfillSkipped;
    }

    public int reasonLogCount() {
        return backfill.reasonLog().size();
    }

    // ---------- 治理（3.8） ----------

    /** 质量门禁裁决（只裁决、不提交；提交由调用方在同一逻辑时钟下完成）。 */
    public QualityGate.Verdict qualityGateCheck(QualityGate.Batch batch, long expectedRows, long freshnessAt) {
        QualityGate.Verdict verdict = gate.check(batch, expectedRows, freshnessAt);
        lastGateLabel = verdict.label();
        lastGateFailedChecks = verdict.failedCount();
        return verdict;
    }

    public QualityGate qualityGate() {
        return gate;
    }

    public String lastGateLabel() {
        return lastGateLabel;
    }

    public long lastGateFailedChecks() {
        return lastGateFailedChecks;
    }

    /** 登记列级血缘（校验分层方向由 {@link Lineage} 负责）。 */
    public Lineage lineage(String outputTable, String outputColumn, String inputTable, String inputColumn,
                           String expression) {
        if (lineage == null) {
            lineage = new Lineage(model);
        }
        Lineage.ColumnRef out = new Lineage.ColumnRef(model.require(layerRef(outputTable)), outputColumn);
        Lineage.ColumnRef in = new Lineage.ColumnRef(model.require(layerRef(inputTable)), inputColumn);
        lineage.derive(out, in, expression);
        return lineage;
    }

    public Lineage lineage() {
        return lineage;
    }

    private TableRef layerRef(String table) {
        return new TableRef(table, TableRef.parseLayer(table));
    }

    public int lineageNodeCount() {
        return lineage == null ? 0 : lineage.nodes().size();
    }

    /** 血缘里能回溯到的 ODS 源列数（合规追溯的读数）。 */
    public int odsSourceColumnCount() {
        if (lineage == null) {
            return 0;
        }
        Set<Lineage.ColumnRef> ods = new TreeSet<>();
        for (Lineage.ColumnRef node : lineage.nodes()) {
            if (node.table().layer() == Layer.ODS) {
                ods.add(node);
            }
        }
        return ods.size();
    }

    /** 成本一屏的数据源（与 {@link OpsConsole} 同源）。 */
    public CostReport.Snapshot costs() {
        return costs.snapshot(filesByTable(), lastScanBytes, lastScanFullBytes, layout, compactionPlans);
    }

    public CostReport costReport() {
        return costs;
    }

    /** 运维一屏（与 {@link #costs()} 共用读数）。 */
    public OpsConsole ops() {
        if (opsConsole == null) {
            opsConsole = new OpsConsole(this);
        }
        return opsConsole;
    }

    // ---------- 全平台读数 ----------

    /** 每张表当前的文件清单（按登记序，保证输出可复现）。 */
    public Map<TableRef, List<DataFile>> filesByTable() {
        Map<TableRef, List<DataFile>> byTable = new LinkedHashMap<>();
        for (TableRef ref : model.tables()) {
            TableFormat format = formats.get(ref.table());
            byTable.put(ref, format == null ? List.of() : format.current().files());
        }
        return byTable;
    }

    public int tableCount() {
        return model.tableCount();
    }

    public int fileCount() {
        return filesByTable().values().stream().mapToInt(List::size).sum();
    }

    public int partitionCount() {
        return filesByTable().values().stream()
                .mapToInt(files -> layout.group(files).size())
                .sum();
    }

    public long storageBytes() {
        return filesByTable().values().stream()
                .flatMap(List::stream)
                .mapToLong(DataFile::bytes)
                .sum();
    }

    /** 全平台快照列表（按表）。 */
    public Map<String, List<Snapshot>> snapshots() {
        Map<String, List<Snapshot>> all = new TreeMap<>();
        formats.forEach((name, format) -> all.put(name, format.history()));
        return java.util.Collections.unmodifiableMap(all);
    }

    /** 门面自检：所有表的父链都连续、层依赖全部合法（供 Demo 与运维脚本调用）。 */
    public boolean invariantsHold() {
        for (TableFormat format : formats.values()) {
            if (!format.lineageContinuous()) {
                return false;
            }
        }
        for (WarehouseModel.Dependency dependency : model.dependencies()) {
            if (!dependency.downstream().layer().canReadFrom(dependency.upstream().layer())) {
                return false;
            }
        }
        return true;
    }
}
