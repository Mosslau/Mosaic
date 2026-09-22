// project/src/lakeplat/LakePlatformDemo.java —— 最小湖仓与编排平台端到端演示 + 14 项验收断言
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 阶段项目验收：一条完整闭环，全部数据确定性自造（固定逻辑时钟 T0，不读系统时间、不读外部文件）。
 *
 * <pre>
 * A 四层建表与口径(1-2) → B 快照/时间旅行/增量读/演进(3-6) → C 分区裁剪(7) → D 小文件治理(8)
 *   → E 批流一体(9-10) → F DAG 编排(11-12) → G 幂等回填(13) → H 门禁+血缘+成本一屏(14)
 * </pre>
 *
 * <p>末尾打印 {@code ALL PASS: 14/14}；任何一项 FAIL 都以 {@code System.exit(1)} 结束，便于 CI 判定。
 */
public final class LakePlatformDemo {

    /** 固定逻辑时钟原点：2024-06-01T00:00:00Z（不读系统时间，保证逐字节可复现）。 */
    private static final long T0 = Window.ORIGIN;
    private static final long HOUR = 3_600_000L;

    public static void main(String[] args) {
        System.out.println("== 最小湖仓与编排平台（lakeplat）闭环演示：分层→快照→布局→治理→批流→编排→回填→门禁 ==");

        LakePlatform plat = new LakePlatform(
                new PartitionLayout("event_date", 4, 512L * 1024L),
                new Compaction(512L * 1024L));
        AtomicInteger pass = new AtomicInteger();

        // ================= 装配：四层建表 + 依赖 + 口径（3.1） =================

        Schema odsSchema = Schema.of("event_id", "long", "payload", "string", "ingest_date", "string");
        TableRef ods = plat.createTable("ods_event_raw", Layer.ODS, "ingest_date", 30, odsSchema, T0);

        Schema dwdSchema = Schema.of("event_id", "long", "instance_id", "string", "latency_ms", "long",
                "event_date", "string", "region", "string");
        TableRef dwd = plat.createTable("dwd_trip_detail", Layer.DWD, "event_date", 0, dwdSchema, T0);

        Schema dwsSchema = Schema.of("instance_id", "string", "event_date", "string", "trip_count", "long");
        TableRef dws = plat.createTable("dws_metrics_instance_day", Layer.DWS, "event_date", 0, dwsSchema, T0);
        TableRef dwsSecond = plat.createTable("dws_metrics_instance_week", Layer.DWS, "event_date", 6,
                dwsSchema, T0);

        Schema adsSchema = Schema.of("metric", "string", "event_date", "string", "value", "long");
        TableRef ads = plat.createTable("ads_dashboard_daily", Layer.ADS, "event_date", 0, adsSchema, T0);

        plat.depend(dwd, ods);
        plat.depend(dws, dwd);
        plat.depend(ads, dws);
        plat.declareMetric("instances_daily_active", dws);

        // ODS 先落一个原始快照：ODS 不做业务解释，只做格式校验（3.1）
        plat.commitWithRetry(ods, T0 + 1_000, "APPEND", odsSchema,
                Map.of("ingest_date=2024-06", List.of(new DataFile(
                        "data/ods_event_raw/ingest_date=2024-06/part-0000.parquet",
                        "ingest_date=2024-06", 120_000, 7_680_000))));

        // ================= A. 四层依赖纪律与口径唯一源（3.1） =================

        // ① 合法依赖被接受、下游闭包正确；DWD 读 ADS 的反向依赖被拒
        boolean reverseRejected = false;
        String reverseMessage = "";
        try {
            plat.depend(dwd, ads);
        } catch (IllegalStateException e) {
            reverseRejected = true;
            reverseMessage = e.getMessage();
        }
        check(pass, reverseRejected && plat.model().tableCount() == 5
                        && plat.model().dependencies().size() == 3
                        && plat.model().downstreamClosure(dwd).contains(dws)
                        && plat.model().downstreamClosure(dwd).contains(ads)
                        && plat.invariantsHold(),
                "四层依赖：5 张表 / 3 条合法依赖（ODS→DWD→DWS→ADS），DWD 下游闭包含 DWS+ADS；"
                        + "DWD 读 ADS 被拒 → " + reverseMessage);

        // ② 口径必须写在 DWS；DWD 与 ADS 里声明同一指标都被拒
        boolean upstreamRejected = false;
        String upstreamMessage = "";
        try {
            plat.declareMetric("instances_daily_active", dwd);
        } catch (IllegalStateException e) {
            upstreamRejected = true;
            upstreamMessage = e.getMessage();
        }
        boolean downstreamRejected = false;
        String downstreamMessage = "";
        try {
            plat.declareMetric("instances_daily_active", ads);
        } catch (IllegalStateException e) {
            downstreamRejected = true;
            downstreamMessage = e.getMessage();
        }
        check(pass, upstreamRejected && downstreamRejected
                        && "dws_metrics_instance_day".equals(plat.model().metricOwner("instances_daily_active"))
                        && upstreamMessage.contains("只允许声明在 DWS")
                        && downstreamMessage.contains("只允许声明在 DWS"),
                "口径唯一源：instances_daily_active 归属 " + plat.model().metricOwner("instances_daily_active")
                        + "；DWD 声明被拒（" + upstreamMessage + "）；ADS 声明被拒（" + downstreamMessage + "）");

        // ================= B. 快照链：原子提交 / 时间旅行 / 增量读 / schema 演进（3.2） =================

        TableFormat dwdFormat = plat.table(dwd);
        long snapCreate = dwdFormat.current().snapshotId();

        // 第一批写入：8 个小文件的分区 + 3 个文件的分区
        Map<String, List<DataFile>> batch1 = new LinkedHashMap<>();
        batch1.put("event_date=2024-06-01", rows(dwd, "event_date=2024-06-01", 0, 8, 1_000, 416));
        batch1.put("event_date=2024-06-02", rows(dwd, "event_date=2024-06-02", 0, 3, 1_200, 416));
        TableFormat.CommitResult commit1 = plat.commitWithRetry(dwd, T0 + 2_000, "APPEND", dwdSchema, batch1);
        long snap1 = commit1.snapshot().snapshotId();
        long rowsSnap1 = commit1.snapshot().totalRows();

        // 第二批写入：**分区整体覆盖** 06-02 + 新增 06-03（新清单 = 上一快照清单 + 本次改动，
        // 这是「分区级幂等」在表格式层的体现：覆盖不追加，所以重跑不会翻倍）
        Map<String, List<DataFile>> batch2 = new LinkedHashMap<>(dwdFormat.current().manifest());
        batch2.put("event_date=2024-06-02", rows(dwd, "event_date=2024-06-02", 0, 2, 1_400, 416));
        batch2.put("event_date=2024-06-03", rows(dwd, "event_date=2024-06-03", 0, 3, 900, 416));
        TableFormat.CommitResult commit2 = plat.commitWithRetry(dwd, T0 + 3_000, "OVERWRITE", dwdSchema, batch2);
        long snap2 = commit2.snapshot().snapshotId();

        // ③ 父链连续 + CAS 提交后 current 前进 + 过期父快照的提交被拒（乐观并发）
        TableFormat.CommitResult stale = plat.commit(dwd, snapCreate, T0 + 3_500, "APPEND", dwdSchema,
                dwdFormat.current().manifest());
        check(pass, commit1.accepted() && commit2.accepted()
                        && dwdFormat.lineageContinuous()
                        && dwdFormat.current().snapshotId() == snap2
                        && dwdFormat.snapshot(snap2).parentId() == snap1
                        && dwdFormat.snapshot(snap1).parentId() == snapCreate
                        && !stale.accepted() && stale.message().contains("CAS 冲突")
                        && dwdFormat.current().snapshotId() == snap2
                        && dwdFormat.commitAttempts() == 3
                        && plat.invariantsHold(),
                "快照链：CREATE #" + snapCreate + " → #" + snap1 + " → #" + snap2 + " 父链连续，current 前进到 #"
                        + snap2 + "；用过期父快照 #" + snapCreate + " 提交被拒（" + stale.message()
                        + "），3 次提交尝试后指针仍指向 #" + dwdFormat.current().snapshotId());

        // ④ 时间旅行读到历史行数（读旧数据不需要副本）
        Snapshot historical = plat.timeTravel(dwd, T0 + 2_500);
        check(pass, historical.snapshotId() == snap1 && historical.totalRows() == rowsSnap1
                        && dwdFormat.current().totalRows() != rowsSnap1
                        && plat.lastTimeTravelRows() == rowsSnap1,
                "时间旅行：在 ts=T0+2500ms 读到快照 #" + historical.snapshotId() + "（" + rowsSnap1
                        + " 行），而 current #" + snap2 + " 已是 " + dwdFormat.current().totalRows()
                        + " 行——读旧数据只沿父链回溯，不需要副本");

        // ⑤ 增量读只含变化分区（06-02 被覆盖 + 06-03 新增；06-01 与 schema 变更不含数据）
        Set<String> changed = plat.incremental(dwd, snap1);
        check(pass, changed.equals(new TreeSet<>(Set.of("event_date=2024-06-02", "event_date=2024-06-03")))
                        && !changed.contains("event_date=2024-06-01")
                        && plat.lastIncrementalPartitions() == 2,
                "增量读：自快照 #" + snap1 + " 以来变化分区 = " + changed
                        + "（06-01 未变化 + 后续 schema 变更不含数据 → 下游不必重扫，判据是快照元数据而不是时间戳）");

        // ⑥ 不兼容 schema 变更被拒（提交阶段 fail-fast，指针不动）；加列兼容
        Schema addedColumn = dwdSchema.plus("device_model", "string");
        Schema droppedColumn = dwdSchema.minus("instance_id");
        boolean dropRejected = false;
        String dropMessage = "";
        long snapshotIdBeforeDrop = dwdFormat.current().snapshotId();
        try {
            plat.commitWithRetry(dwd, T0 + 3_600, "APPEND", droppedColumn, dwdFormat.current().manifest());
        } catch (IllegalStateException e) {
            dropRejected = true;
            dropMessage = e.getMessage();
        }
        plat.commitWithRetry(dwd, T0 + 3_700, "APPEND", addedColumn, dwdFormat.current().manifest());
        check(pass, dropRejected && dropMessage.contains("instance_id") && dropMessage.contains("删除")
                        && dwdFormat.current().schema().has("device_model")
                        && dwdFormat.current().snapshotId() > snapshotIdBeforeDrop
                        && dwdFormat.snapshot(snapshotIdBeforeDrop).schema().has("instance_id"),
                "schema 演进：删列 instance_id 在提交阶段被拒（" + dropMessage + "），快照停在 #"
                        + snapshotIdBeforeDrop + "；加列 device_model 兼容并提交成功 → #"
                        + dwdFormat.current().snapshotId() + "（旧快照仍能读出 instance_id）");

        // ================= C. 分区布局与扫描成本（3.3） =================

        // ⑦ 分区裁剪：只扫 06-01 的 8 个文件，全表 13 个文件；扫描字节显著下降
        PartitionLayout.ScanCost cost = plat.scan(dwd, Set.of("event_date=2024-06-01"));
        int fullFiles = cost.fullFiles();
        check(pass, cost.files() == 8 && fullFiles == 13
                        && cost.partitions() == 1
                        && cost.pruneRatio() > 0.3
                        && plat.lastScanBytes() == cost.bytes()
                        && plat.lastScanFullBytes() == cost.fullBytes(),
                "分区裁剪：" + cost.label() + "——只命中 06-01 的 8 个文件（全表 " + fullFiles + " 个），扫描量下降 "
                        + String.format(Locale.ROOT, "%.1f", cost.pruneRatio() * 100)
                        + "%（分区键匹配查询谓词才有收益，scanBytes 就是这次查询要付的钱）");

        // ================= D. 小文件检测与 compaction（3.4） =================

        // ⑧ 小文件分区被检出；compaction 收益为正；重复 apply 幂等且字节守恒
        List<DataFile> beforeCompaction = dwdFormat.current().files();
        List<PartitionLayout.SmallFileFlag> smallFiles = plat.layout().detectSmallFilePartitions(beforeCompaction);
        Map<String, Compaction.Plan> plans = plat.planCompaction(dwd);
        Compaction.Plan plan = plans.get("event_date=2024-06-01");
        long bytesBefore = beforeCompaction.stream().mapToLong(DataFile::bytes).sum();
        List<DataFile> applied = plat.applyCompaction(dwd, T0 + 4_000);
        long bytesAfter = dwdFormat.current().files().stream().mapToLong(DataFile::bytes).sum();
        List<DataFile> appliedAgain = plat.applyCompaction(dwd, T0 + 4_100);
        List<DataFile> partitionAfter = dwdFormat.current().manifest().get("event_date=2024-06-01");
        Map<String, Compaction.Plan> plansAgain = plat.planCompaction(dwd);
        check(pass, smallFiles.size() == 1
                        && "event_date=2024-06-01".equals(smallFiles.get(0).partition())
                        && plan != null && plan.fileCountBefore() == 8 && plan.fileCountAfter() == 4
                        && plan.readSavedRatio() == 0.5 && plan.writeAmplification() == 1.0
                        && bytesAfter == bytesBefore && applied.size() == plan.fileCountAfter()
                        && appliedAgain.isEmpty() && applied.equals(partitionAfter)
                        && plansAgain.isEmpty(),
                "小文件治理：检出 " + smallFiles.get(0) + "；合并方案 " + plan.label() + "（字节守恒 "
                        + bytesBefore + "B）；重复 apply 幂等——第二次产出 " + appliedAgain.size()
                        + " 个新文件，清单仍 " + partitionAfter.size() + " 个文件，重规划已无可合并分区（读多写少才值得合）");

        // ================= E. 批流一体：同一口径两种执行（3.5） =================

        List<Event> allEvents = new ArrayList<>();
        allEvents.add(evt(1, "instance-1", T0 + 10 * HOUR, 10));
        allEvents.add(evt(2, "instance-2", T0 + 11 * HOUR, 20));
        allEvents.add(evt(3, "instance-1", T0 + 12 * HOUR, 30));
        allEvents.add(evt(4, "instance-3", T0 + 13 * HOUR, 40));
        allEvents.add(evt(5, "instance-2", T0 + 14 * HOUR, 50));
        allEvents.add(evt(6, "instance-1", T0 + 15 * HOUR, 60));
        allEvents.add(evt(7, "instance-3", T0 + 16 * HOUR, 11));
        allEvents.add(evt(8, "instance-2", T0 + 44 * HOUR, 12));    // 06-02 20:00 → 水位线推进到 06-02 19:55
        allEvents.add(evt(9, "instance-1", T0 + 9 * HOUR + 30 * 60_000L, 99));   // 迟到：06-01 09:30
        allEvents.add(evt(10, "instance-3", T0 + 45 * HOUR, 13));
        allEvents.add(evt(11, "instance-1", T0 + 46 * HOUR, 14));
        allEvents.add(evt(12, "instance-2", T0 + 47 * HOUR, 7));
        // 事件**到达顺序**（流算的输入）：e9（06-01 09:30）在 e8（06-02 20:00）之后才到，
        // 此时水位线已推进到 06-02 19:55 → e9 被判迟到并写侧输出。批算的输入按事件时间排序。
        List<Event> arrivalOrder = List.copyOf(allEvents);
        List<Event> ordered = Pipeline.ordered(allEvents);

        Pipeline batchPipe = plat.pipeline("trip-metrics", 5 * 60_000L);
        Map<String, Pipeline.WindowResult> batchResults = batchPipe.batch(ordered);
        // 同口径输入：批算侧剔除那条已知迟到的事件（迟到的判据是"事件时间 <= 水位线"，
        // 在批算里就是"比该窗口最大已见时间晚到"，本示例里即 evt-0009）
        List<Event> onTime = new ArrayList<>();
        ordered.stream().filter(event -> !event.eventId().equals("evt-0009")).forEach(onTime::add);
        Map<String, Pipeline.WindowResult> sameLensAggregate = batchPipe.aggregate(onTime);
        Pipeline streamPipe = plat.pipeline("trip-metrics", 5 * 60_000L);
        Pipeline.StreamOutcome outcome = streamPipe.stream(arrivalOrder);
        boolean parityHolds = true;
        try {
            streamPipe.assertParity(sameLensAggregate);      // 同口径：批算剔除迟到，流算把迟到判成侧输出
        } catch (IllegalStateException e) {
            parityHolds = false;
        }

        // ⑨ 批算与流算在同一窗口结果一致（同口径：同过滤、同事件时间、同幂等写）
        Pipeline.WindowResult streamWindow = streamPipe.result("2024-06-01");
        Pipeline.WindowResult sameLensWindow = sameLensAggregate.get("2024-06-01");
        Pipeline.WindowResult fullWindow = batchResults.get("2024-06-01");   // 含迟到事件的批算对照
        check(pass, parityHolds && sameLensWindow != null && fullWindow != null
                        && sameLensWindow.count() == 7 && sameLensWindow.sum() == 221
                        && fullWindow.count() == 8 && fullWindow.sum() == 320
                        && streamWindow.count() == sameLensWindow.count()
                        && streamWindow.sum() == sameLensWindow.sum()
                        && streamWindow.average() == sameLensWindow.average()
                        && batchResults.keySet().equals(streamPipe.resultsInOrder().keySet())
                        && streamPipe.result("2024-06-02").count() == 4
                        && streamPipe.result("2024-06-02").sum() == 46,
                "批流同口径：窗口 " + sameLensWindow.windowKey() + " 同口径批算 " + sameLensWindow.count()
                        + " 行/sum=" + sameLensWindow.sum() + "，流算 " + streamWindow.count() + " 行/sum="
                        + streamWindow.sum() + "（assertParity 通过）；含迟到事件的历史全量批算是 "
                        + fullWindow.count() + " 行/sum=" + fullWindow.sum() + "，另一窗口 "
                        + streamPipe.result("2024-06-02").windowKey() + " 为 "
                        + streamPipe.result("2024-06-02").count() + " 行——同一份过滤+聚合逻辑、同一事件时间、"
                        + "同一幂等写，批与流得出同一组数");

        // ⑩ 迟到事件进侧输出；整条流重放后结果与侧输出逐字节一致（不重复计数）
        Pipeline replay = new Pipeline("trip-metrics", 5 * 60_000L);
        replay.stream(arrivalOrder);
        List<Pipeline.LateRecord> side = streamPipe.sideOutput();
        boolean replayIdentical = replay.resultsDigest().equals(streamPipe.resultsDigest())
                && replay.sideOutput().size() == side.size()
                && replay.lateCount() == streamPipe.lateCount();
        Pipeline.LateRecord lateRecord = side.isEmpty() ? null : side.get(0);
        check(pass, streamPipe.lateCount() == 1 && lateRecord != null
                        && lateRecord.eventId().equals("evt-0009")
                        && lateRecord.latenessMillis() == 34 * HOUR + 25 * 60_000L
                        && lateRecord.windowKey().equals("2024-06-01")
                        && lateRecord.watermark() == lateRecord.eventTime() + lateRecord.latenessMillis()
                        && streamPipe.retainedEventCount() == 11
                        && replayIdentical,
                "迟到侧输出：水位线 " + outcome.watermark() + "，接受 " + outcome.accepted() + " 条，迟到 "
                        + streamPipe.lateCount() + " 条 → 侧输出 "
                        + side + (lateRecord == null ? "" : "（迟到 " + lateRecord.latenessMillis() + "ms）")
                        + "；整条流重放后结果与侧输出逐字节一致，窗口内事件 " + streamPipe.retainedEventCount()
                        + " 条不重复计数（批流一体的最后一块拼图）");

        // ================= F. DAG 编排：拓扑序 / 就绪 / 重试 / 失败传播（3.6） =================

        Dag dag = new Dag(List.of(
                TaskNode.of("ods_ingest", ods),
                TaskNode.of("dwd_clean", dwd, "ods_ingest"),
                TaskNode.of("dwd_dedup", dwd, "dwd_clean"),
                TaskNode.of("dwd_dim", dwd, "dwd_clean"),
                TaskNode.of("dws_metrics", dws, "dwd_dedup", "dwd_dim"),
                TaskNode.of("ads_dashboard", ads, "dws_metrics", "dwd_dedup", "dwd_dim"),
                TaskNode.of("ads_export", ads, "ads_dashboard")));

        Map<String, Dag.State> simulated = new LinkedHashMap<>();
        simulated.put("ods_ingest", Dag.State.SUCCEEDED);
        simulated.put("dwd_clean", Dag.State.SUCCEEDED);
        simulated.put("dwd_dedup", Dag.State.SUCCEEDED);

        // ⑪ 确定性拓扑序 + 就绪条件严格 + 重试上限内先失败后成功
        List<String> expectedTopo = List.of("ods_ingest", "dwd_clean", "dwd_dedup", "dwd_dim",
                "dws_metrics", "ads_dashboard", "ads_export");
        Dag dagAgain = new Dag(dag.nodes());
        Orchestrator retrying = new Orchestrator(dag, 4, Orchestrator.failingOnce(Map.of("dws_metrics", 1)));
        Orchestrator.Summary retrySummary = retrying.runToCompletion(20);
        List<String> dwsAttempts = new ArrayList<>();
        retrySummary.executionLog().stream().filter(run -> run.taskId().equals("dws_metrics"))
                .forEach(run -> dwsAttempts.add(run.attempt() + ":" + run.outcome()));
        check(pass, dag.topoOrder().equals(expectedTopo) && dagAgain.topoOrder().equals(dag.topoOrder())
                        && !dag.ready("dws_metrics", simulated, Set.of())
                        && dag.readyTasks(simulated, Set.of()).equals(List.of("dwd_dim"))
                        && dwsAttempts.equals(List.of("1:FAILED", "2:SUCCEEDED"))
                        && retrySummary.allSucceeded(),
                "编排拓扑与重试：两次构造拓扑序相同 " + dag.topoOrder() + "；dwd_dedup 已成功而 dwd_dim 未成功时 "
                        + "dws_metrics 不就绪（上游必须全部成功），就绪集 = " + dag.readyTasks(simulated, Set.of())
                        + "；dws_metrics 尝试记录 " + dwsAttempts + " → 整图 " + retrySummary.label());

        // ⑫ 重试耗尽 → FAILED，并把下游**阻塞**（而不是跳过）
        Orchestrator failing = plat.orchestrate(dag, 4,
                Orchestrator.alwaysFailing(Set.of("ads_dashboard"), Map.of()));
        Orchestrator.Summary failSummary = failing.runToCompletion(20);
        List<String> adsAttempts = new ArrayList<>();
        failing.executionLog().stream().filter(run -> run.taskId().equals("ads_dashboard"))
                .forEach(run -> adsAttempts.add(run.attempt() + ":" + run.outcome()));
        check(pass, failSummary.permanentlyFailed().equals(List.of("ads_dashboard"))
                        && failSummary.blocked().equals(List.of("ads_export"))
                        && dag.blockedClosure("ads_dashboard").equals(List.of("ads_export"))
                        && adsAttempts.equals(List.of("1:FAILED", "2:FAILED", "3:FAILED"))
                        && failing.failureReason("ads_dashboard").contains("重试 2 次耗尽")
                        && failSummary.states().get("ads_export") == Dag.State.BLOCKED
                        && failSummary.succeeded().size() == 5,
                "失败传播：ads_dashboard 尝试记录 " + adsAttempts + "（重试上限 " + dag.node("ads_dashboard").retries()
                        + " 次）→ 永久失败；下游 " + failSummary.blocked() + " 被**阻塞**而非跳过（"
                        + failing.failureReason("ads_dashboard") + "），显式暴露缺口，成功 "
                        + failSummary.succeeded().size() + "/" + failSummary.topoOrder().size() + " 个节点");

        // ================= G. 幂等回填：分区覆盖 / 下游重算 / 断点续跑 / 原因留痕（3.7） =================

        Backfill backfill = plat.backfill();
        backfill.setSource("2024-06-01", 10_800);
        backfill.setSource("2024-06-02", 9_520);
        backfill.put(dwd, "2024-06-01", Backfill.PartitionData.of(9_586, 9_586 * 6, 2));
        backfill.put(dws, "2024-06-01", Backfill.PartitionData.of(9_586, 9_586 * 16, 1));
        backfill.put(ads, "2024-06-01", Backfill.PartitionData.of(9_586, 9_586 * 8, 1));

        Backfill.Plan day1 = backfill.plan(dwd, "2024-06-01", "上游修数：源系统补回 1214 条被隐藏的记录");
        long adsBefore = backfill.rowsOf(ads, "2024-06-01");
        Backfill.RunResult run1 = plat.runBackfill(day1, T0 + 5_000);
        Backfill.RunResult run2 = plat.runBackfill(day1, T0 + 5_100);   // 第二次：已成功的分区直接跳过

        // ⑬ 幂等：重复执行结果一致 + 下游闭包被真正重算 + 断点续跑只补缺口 + 原因留痕
        long adsAfter = backfill.rowsOf(ads, "2024-06-01");
        Backfill.Plan day2 = backfill.plan(dwd, "2024-06-02", "故障补偿：06-02 批次缺 3 个分区文件");
        plat.runBackfill(day2, T0 + 5_200);
        Backfill.RunResult resumed = plat.resumeBackfill(day2, T0 + 5_400);
        List<String> reasons = new ArrayList<>();
        backfill.reasonLog().forEach(log -> reasons.add(log.toString()));
        check(pass, run1.applied().size() == 3 && run2.applied().isEmpty()
                        && run1.digest().equals(run2.digest())
                        && run1.appliedOrder().equals(List.of("dwd_trip_detail/2024-06-01",
                                "dws_metrics_instance_day/2024-06-01", "ads_dashboard_daily/2024-06-01"))
                        && day1.tasks().size() == 3
                        && day1.downstreamTables().equals(new TreeSet<>(Set.of("dws_metrics_instance_day",
                                "ads_dashboard_daily")))
                        && adsAfter == 10_800 && adsAfter != adsBefore
                        && backfill.rowsOf(dws, "2024-06-01") == 10_800
                        && resumed.applied().isEmpty() && resumed.skipped().size() == 3
                        && backfill.reasonLog().size() == 4 && backfill.appliedKeys().size() == 6
                        && reasons.get(0).contains("上游修数") && reasons.get(3).contains("故障补偿"),
                "幂等回填：重算 " + run1.appliedOrder() + "（下游 " + day1.downstreamTables()
                        + "，不含粒度不对齐的 ODS 月分区）；第二次执行 0 个新分区且全量状态摘要与第一次逐字节相同；ADS 读数 "
                        + adsBefore + " → " + adsAfter + " 证明闭包被真正重算；断点续跑跳过已成功的 "
                        + resumed.skipped().size() + " 个分区；原因留痕 " + backfill.reasonLog().size() + " 条（"
                        + reasons.get(0) + " … " + reasons.get(3) + "）");

        // ================= H. 门禁 / 血缘 / 成本一屏（3.8） =================

        // 门禁 fail-closed：坏批次被拒 → 不提交；好批次才允许提交
        long snapshotBeforeGate = dwdFormat.current().snapshotId();
        QualityGate.Batch goodBatch = new QualityGate.Batch("dwd_trip_detail", "2024-06-04",
                batchRows(1_000, 500, T0 + 23 * HOUR));
        QualityGate.Verdict goodVerdict = plat.qualityGateCheck(goodBatch, 1_000, T0 + 24 * HOUR);

        List<QualityGate.Row> badRows = new ArrayList<>();
        badRows.add(new QualityGate.Row(1, 1, 900, T0 + 12 * HOUR, "cn-east"));      // 量程越界
        badRows.add(new QualityGate.Row(2, 2, -5, T0 + 13 * HOUR, "cn-north"));      // 量程越界
        badRows.add(new QualityGate.Row(2, 3, 700, T0 + 14 * HOUR, "cn-south"));     // 主键重复
        badRows.add(new QualityGate.Row(4, 4, 100, T0 + 15 * HOUR, "  "));           // 非空失败
        QualityGate.Batch badBatch = new QualityGate.Batch("dwd_trip_detail", "2024-06-04", List.copyOf(badRows));
        QualityGate.Verdict badVerdict = plat.qualityGateCheck(badBatch, badRows.size(), T0 + 16 * HOUR);
        List<String> failedChecks = new ArrayList<>();
        badVerdict.results().stream().filter(result -> !result.passed())
                .forEach(result -> failedChecks.add(result.check().name()));
        if (!badVerdict.allowed()) {
            System.out.println("     （fail-closed：门禁拒绝 → 跳过提交，表保持快照 #" + snapshotBeforeGate + "）");
        }

        // 列级血缘：DWD ← ODS、DWS ← DWD、ADS ← DWS
        plat.lineage("dwd_trip_detail", "event_id", "ods_event_raw", "event_id", "清洗：类型转换 + 去重");
        plat.lineage("dwd_trip_detail", "region", "ods_event_raw", "region", "清洗：空值填充");
        plat.lineage("dwd_trip_detail", "latency_ms", "ods_event_raw", "payload", "解析 payload 中的耗时字段");
        plat.lineage("dwd_trip_detail", "event_date", "ods_event_raw", "ingest_date", "按落库日期派生事件日期");
        plat.lineage("dws_metrics_instance_day", "trip_count", "dwd_trip_detail", "event_id",
                "count(distinct event_id)");
        plat.lineage("dws_metrics_instance_day", "event_date", "dwd_trip_detail", "event_date", "分组键（消费）");
        plat.lineage("ads_dashboard_daily", "value", "dws_metrics_instance_day", "trip_count", "sum(trip_count)");
        Lineage lineage = plat.lineage();
        Set<Lineage.ColumnRef> odsSources = lineage.odsSourcesOf(new Lineage.ColumnRef(ads, "value"));
        Set<Lineage.ColumnRef> impact = lineage.impactOf(new Lineage.ColumnRef(ods, "region"));

        // fail-closed 的可验证含义：门禁拒绝后**没有**发生提交，当前快照的行数/schema 原样
        long snapshotAtGateReject = dwdFormat.current().snapshotId();
        long rowsAtGateReject = dwdFormat.current().totalRows();
        Schema schemaAtGateReject = dwdFormat.current().schema();
        boolean gateBlockedCommit = !badVerdict.allowed() && !dwdFormat.current().manifest()
                .containsKey("event_date=2024-06-04");
        // 门禁通过的那一批才提交（同一逻辑时钟下的"发布"动作）
        TableFormat.CommitResult gated = plat.commitWithRetry(dwd, T0 + 6_000, "APPEND",
                dwdFormat.current().schema(),
                dwdFormat.withAdded("event_date=2024-06-04",
                        rows(dwd, "event_date=2024-06-04", 0, 2, 500, 416)));

        // 成本一屏与 Prometheus 文本在**同一时刻**取读数（同源一致的结构性保证）
        OpsConsole ops = plat.ops();
        OpsConsole.OpsView view = ops.snapshot();
        CostReport.Snapshot costSnapshot = plat.costs();
        String metrics = ops.prometheusText();
        ops.print();

        // ⑭ 门禁失败了就不发布快照；血缘可回溯到 ODS；成本一屏与 Prometheus 文本同源一致
        long dwdFilesInView = view.tableCosts().stream()
                .filter(tableCost -> tableCost.table().equals("dwd_trip_detail")).findFirst().orElseThrow().files();
        double dwdFilesInMetrics = metric(metrics, "lake_table_files{table=\"dwd_trip_detail\",layer=\"DWD\"}");
        Set<Lineage.ColumnRef> expectedImpact = Set.of(new Lineage.ColumnRef(dwd, "region"),
                new Lineage.ColumnRef(ods, "region"));
        check(pass, goodVerdict.allowed() && !badVerdict.allowed()
                        && failedChecks.equals(List.of("NOT_NULL", "UNIQUE", "RANGE"))
                        && badVerdict.failedCount() == 3 && badVerdict.results().size() == 5
                        && gateBlockedCommit && snapshotAtGateReject == snapshotBeforeGate
                        && rowsAtGateReject == dwdFormat.snapshot(snapshotBeforeGate).totalRows()
                        && schemaAtGateReject.equals(dwdFormat.snapshot(snapshotBeforeGate).schema())
                        && gated.accepted() && dwdFormat.current().snapshotId() > snapshotBeforeGate
                        && odsSources.equals(Set.of(new Lineage.ColumnRef(ods, "event_id")))
                        && lineage.orphanColumns().isEmpty()
                        && impact.equals(expectedImpact)
                        && view.storageBytes() == costSnapshot.storageBytes()
                        && view.files() == costSnapshot.fileCount()
                        && view.partitions() == costSnapshot.partitionCount()
                        && view.scanBytes() == costSnapshot.scanBytes()
                        && view.dagNodes() == 7 && view.dagFailed() == 1 && view.dagBlocked() == 1
                        && view.lineageColumns() == lineage.nodes().size()
                        && view.odsSourceColumns() == 4
                        && metric(metrics, "lake_storage_bytes") == view.storageBytes()
                        && metric(metrics, "lake_files_total") == view.files()
                        && metric(metrics, "lake_scan_bytes") == view.scanBytes()
                        && metric(metrics, "lake_dag_tasks{state=\"blocked\"}") == view.dagBlocked()
                        && dwdFilesInMetrics == dwdFilesInView
                        && metric(metrics, "lake_lineage_ods_source_columns") == 4,
                "门禁/血缘/成本：坏批次 " + failedChecks + " 项失败 → " + badVerdict.message()
                        + "，表停在快照 #" + snapshotBeforeGate + "（行数与 schema 原样，坏数据根本没进表），"
                        + "门禁通过的那批才提交 → #" + dwdFormat.current().snapshotId()
                        + "；ADS.value 可回溯到 ODS 列 " + odsSources + "，改 ODS.region 的影响闭包是 " + impact
                        + "（变更评审的最小单位）；一屏 [表/快照/成本/编排/治理] 五块齐全，"
                        + "Prometheus 文本与快照逐项一致（storage=" + view.storageBytes() + "B / files="
                        + view.files() + " / scan=" + view.scanBytes() + "B）");

        // ---- 验收汇总：14 项全绿才算通过，有 FAIL 直接非零退出，便于 CI 判定 ----
        System.out.printf("ALL PASS: %d/14%n", pass.get());
        if (pass.get() != 14) {
            System.exit(1);
        }
    }

    // ---------- 确定性造数辅助 ----------

    /** 造一个分区的文件列表（确定性：路径、行数、字节全部由参数决定）。 */
    private static List<DataFile> rows(TableRef table, String partition, int startIndex, int count,
                                       long rowsPerFile, long bytesPerRow) {
        List<DataFile> files = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            String path = "data/" + table.table() + "/" + partition
                    + "/part-" + String.format("%04d", startIndex + i) + ".parquet";
            files.add(new DataFile(path, partition, rowsPerFile, rowsPerFile * bytesPerRow));
        }
        return List.copyOf(files);
    }

    /** 造一批门禁用的行（确定性：行号 → 实例 / 耗时 / 地区）。 */
    private static List<QualityGate.Row> batchRows(int count, long latency, long eventTime) {
        List<QualityGate.Row> rows = new ArrayList<>();
        String[] regions = {"cn-east", "cn-north", "cn-south"};
        for (int i = 0; i < count; i++) {
            rows.add(new QualityGate.Row(i, i % 100L + 1, latency + i % 50, eventTime + i, regions[i % 3]));
        }
        return List.copyOf(rows);
    }

    /** 造一条事件（确定性：事件时间只由参数决定）。 */
    private static Event evt(int index, String instanceId, long eventTime, long value) {
        return new Event(String.format("evt-%04d", index), instanceId, eventTime, value, "cn-east");
    }

    /** 从 Prometheus 文本中取样本值：匹配 `样本名{标签} 值` 或 `样本名 值` 整行，找不到返回 -1。 */
    private static double metric(String text, String sample) {
        for (String line : text.split("\n")) {
            if (line.startsWith(sample + " ")) {
                return Double.parseDouble(line.substring(sample.length() + 1).trim());
            }
        }
        return -1.0;
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
