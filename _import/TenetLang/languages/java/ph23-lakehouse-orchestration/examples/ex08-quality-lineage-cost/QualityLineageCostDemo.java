// languages/java/ph23-lakehouse-orchestration/examples/ex08-quality-lineage-cost/QualityLineageCostDemo.java —— 门禁 fail-closed、列级血缘、成本一屏与 Prometheus 文本的同源自检
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex08 *.java && java -cp /tmp/ph23-ex08 QualityLineageCostDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：9/9 PASS）
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class QualityLineageCostDemo {

    /** Prometheus 文本样本行语法：可选的一组 label="value"，末尾是数值（与 ph22 ex08 同一套自检）。 */
    private static final Pattern SAMPLE = Pattern.compile(
            "^[a-zA-Z_:][a-zA-Z0-9_:]*(\\{[a-zA-Z_][a-zA-Z0-9_]*=\"[^\"]*\""
                    + "(,[a-zA-Z_][a-zA-Z0-9_]*=\"[^\"]*\")*\\})? -?[0-9]+(\\.[0-9]+)?$");

    /** 固定时钟：2024-06-03T12:00:00Z —— 所有鲜度判定都以它为基准，不读系统时间。 */
    private static final long NOW = QualityGate.millis("2024-06-03T12:00:00Z");

    private static final long MINUTE = 60_000L;
    private static final long MB = 1024L * 1024;

    public static void main(String[] args) {
        AtomicInteger pass = new AtomicInteger();
        int total = 9;

        // ---------- 数据（确定性自造）：DWD 事件明细，基线 4 行、量程 [0,3000]、鲜度 6h ----------
        List<QualityGate.Row> good = List.of(
                new QualityGate.Row("e1", "inst-a", NOW - 10 * MINUTE, 120),
                new QualityGate.Row("e2", "inst-b", NOW - 20 * MINUTE, 250),
                new QualityGate.Row("e3", "inst-c", NOW - 30 * MINUTE, 480),
                new QualityGate.Row("e4", "inst-a", NOW - 40 * MINUTE, 990));
        long baseline = good.size();

        // 五批「各坏一类」的数据，用来证明五类检查各自都能拦下对应坏数据
        List<QualityGate.Row> nullBad = List.of(
                new QualityGate.Row("e1", "inst-a", NOW - 10 * MINUTE, 120),
                new QualityGate.Row("", "inst-b", NOW - 20 * MINUTE, 250),
                new QualityGate.Row("e3", "inst-c", NOW - 30 * MINUTE, 480),
                new QualityGate.Row("e4", "inst-a", NOW - 40 * MINUTE, 990));
        List<QualityGate.Row> duplicateBad = List.of(
                new QualityGate.Row("e1", "inst-a", NOW - 10 * MINUTE, 120),
                new QualityGate.Row("e1", "inst-b", NOW - 20 * MINUTE, 250),
                new QualityGate.Row("e3", "inst-c", NOW - 30 * MINUTE, 480),
                new QualityGate.Row("e4", "inst-a", NOW - 40 * MINUTE, 990));
        List<QualityGate.Row> rangeBad = List.of(
                new QualityGate.Row("e1", "inst-a", NOW - 10 * MINUTE, 120),
                new QualityGate.Row("e2", "inst-b", NOW - 20 * MINUTE, 250),
                new QualityGate.Row("e3", "inst-c", NOW - 30 * MINUTE, 9_999),
                new QualityGate.Row("e4", "inst-a", NOW - 40 * MINUTE, 990));
        List<QualityGate.Row> countBad = List.of(
                new QualityGate.Row("e1", "inst-a", NOW - 10 * MINUTE, 120),
                new QualityGate.Row("e2", "inst-b", NOW - 20 * MINUTE, 250),
                new QualityGate.Row("e3", "inst-c", NOW - 30 * MINUTE, 480),
                new QualityGate.Row("e4", "inst-a", NOW - 40 * MINUTE, 990),
                new QualityGate.Row("e5", "inst-d", NOW - 11 * MINUTE, 130),
                new QualityGate.Row("e6", "inst-e", NOW - 21 * MINUTE, 260),
                new QualityGate.Row("e7", "inst-f", NOW - 31 * MINUTE, 490),
                new QualityGate.Row("e8", "inst-g", NOW - 41 * MINUTE, 1_000));
        List<QualityGate.Row> staleBad = List.of(
                new QualityGate.Row("e1", "inst-a", NOW - 20 * 60 * MINUTE, 120),
                new QualityGate.Row("e2", "inst-b", NOW - 21 * 60 * MINUTE, 250),
                new QualityGate.Row("e3", "inst-c", NOW - 22 * 60 * MINUTE, 480),
                new QualityGate.Row("e4", "inst-a", NOW - 23 * 60 * MINUTE, 990));

        // A) 五类检查各自能单独拦下对应坏数据
        boolean allGood = QualityGate.allPassed(QualityGate.check(good, baseline, NOW));
        boolean nullOnly = QualityGate.onlyFailed(QualityGate.check(nullBad, baseline, NOW), "notNull");
        boolean uniqueOnly = QualityGate.onlyFailed(QualityGate.check(duplicateBad, baseline, NOW), "unique");
        boolean rangeOnly = QualityGate.onlyFailed(QualityGate.check(rangeBad, baseline, NOW), "range");
        boolean countOnly = QualityGate.onlyFailed(QualityGate.check(countBad, baseline, NOW), "rowCountDelta");
        boolean freshOnly = QualityGate.onlyFailed(QualityGate.check(staleBad, baseline, NOW), "freshness");
        check(pass, allGood && nullOnly && uniqueOnly && rangeOnly && countOnly && freshOnly
                        && QualityGate.check(good, baseline, NOW).size() == QualityGate.CHECK_NAMES.size(),
                "五类检查各自拦下对应坏数据：好数据 5/5 通过；空 key→notNull、重复主键→unique、"
                        + "latency=9999→range、行数 8 vs 4→rowCountDelta、20h 前数据→freshness（每批只坏一类）");

        // B) 空批次 fail-closed：没有「全过」这种默认值
        List<QualityGate.GateResult> emptyResults = QualityGate.check(List.of(), baseline, NOW);
        check(pass, QualityGate.failed(emptyResults, "rowCountDelta") && QualityGate.failed(emptyResults, "freshness")
                        && !QualityGate.allPassed(emptyResults),
                "空批次 fail-closed：0 行的批次在 rowCountDelta 与 freshness 上判 FAIL，不会静默通过（"
                        + QualityGate.render(emptyResults) + "）");

        // ---------- 门禁接在提交之前：坏数据进不来，表停在上一快照 ----------
        TableCommitGate gate = new TableCommitGate(1L, List.of(), baseline, NOW);
        TableCommitGate.CommitOutcome accepted = gate.commit("load-good", good);
        TableCommitGate.CommitOutcome rejected = gate.commit("load-duplicate", duplicateBad);
        TableCommitGate.CommitOutcome rejectedRange = gate.commit("load-range", rangeBad);
        gate.commit("load-null", nullBad);
        gate.commit("load-count", countBad);
        gate.commit("load-stale", staleBad);
        gate.commit("load-empty", List.of());
        System.out.println("门禁提交历史：");
        System.out.println(gate.renderHistory());

        // C) 门禁失败时提交被拒（快照不变、数据不变）
        check(pass, !rejected.committed() && rejected.allGatePassed() == false
                        && rejected.snapshotBefore() == 2L && rejected.snapshotAfter() == 2L
                        && gate.currentSnapshotId() == 2L
                        && gate.currentRows().equals(good)
                        && rejectedRange.snapshotAfter() == 2L
                        && !rejectedRange.committed(),
                "门禁失败时提交被拒（fail-closed）：重复主键与量程越界的批次都 REJECTED，快照停在 #2，"
                        + "表内容仍是上一批好数据");

        // D) 门禁通过后快照前进
        check(pass, accepted.committed() && accepted.allGatePassed()
                        && accepted.snapshotBefore() == 1L && accepted.snapshotAfter() == 2L
                        && gate.commits() == 1 && gate.rejections() == 6,
                "门禁全过才提交：好批次 #1 → #2，此后 6 次尝试全部被拒（提交 " + gate.commits()
                        + " / 拒绝 " + gate.rejections() + "）");

        // ---------- 列级血缘：由变换声明推导──────────
        Lineage lineage = new Lineage(List.of(
                new Lineage.Transform(
                        Lineage.ColumnRef.parse("dwd.event.instanceId"),
                        List.of(Lineage.ColumnRef.parse("ods.event.instance_id")), "identity"),
                new Lineage.Transform(
                        Lineage.ColumnRef.parse("dwd.event.latencyMs"),
                        List.of(Lineage.ColumnRef.parse("ods.event.latency_ms")), "cast"),
                new Lineage.Transform(
                        Lineage.ColumnRef.parse("dws.dau.instances"),
                        List.of(Lineage.ColumnRef.parse("dwd.event.instanceId")), "count distinct"),
                new Lineage.Transform(
                        Lineage.ColumnRef.parse("ads.dashboard.dau_value"),
                        List.of(Lineage.ColumnRef.parse("dws.dau.instances")), "identity"),
                new Lineage.Transform(
                        Lineage.ColumnRef.parse("ads.dashboard.p99_latency"),
                        List.of(Lineage.ColumnRef.parse("dwd.event.latencyMs")), "percentile 99")));
        System.out.println("列级血缘声明：");
        System.out.println("  " + lineage.renderTransforms().replace("\n", "\n  "));

        Lineage.ColumnRef adsDau = Lineage.ColumnRef.parse("ads.dashboard.dau_value");
        Lineage.ColumnRef odsInstance = Lineage.ColumnRef.parse("ods.event.instance_id");

        // E) 列级血缘可回溯到 ODS 列
        List<Lineage.ColumnRef> upstream = List.copyOf(lineage.upstreamOf(adsDau));
        check(pass, upstream.equals(List.of(
                        Lineage.ColumnRef.parse("ads.dashboard.dau_value"),
                        Lineage.ColumnRef.parse("dwd.event.instanceId"),
                        Lineage.ColumnRef.parse("dws.dau.instances"),
                        Lineage.ColumnRef.parse("ods.event.instance_id")))
                        && lineage.upstreamOf(adsDau).contains(odsInstance),
                "列级血缘可回溯到 ODS：ads.dashboard.dau_value 的上游闭包含 "
                        + lineage.renderUpstreamChain(adsDau));

        // F) 影响分析返回下游列集合
        List<Lineage.ColumnRef> downstream = List.copyOf(lineage.downstreamOf(odsInstance));
        List<Lineage.ColumnRef> latencyDownstream =
                List.copyOf(lineage.downstreamOf(Lineage.ColumnRef.parse("ods.event.latency_ms")));
        check(pass, downstream.equals(List.of(
                        Lineage.ColumnRef.parse("ads.dashboard.dau_value"),
                        Lineage.ColumnRef.parse("dwd.event.instanceId"),
                        Lineage.ColumnRef.parse("dws.dau.instances")))
                        && latencyDownstream.equals(List.of(
                                Lineage.ColumnRef.parse("ads.dashboard.p99_latency"),
                                Lineage.ColumnRef.parse("dwd.event.latencyMs")))
                        && lineage.downstreamOf(adsDau).isEmpty(),
                "影响分析返回下游列集合：改 ods.event.instance_id 会影响 " + downstream
                        + "；改 ods.event.latency_ms 只影响 " + latencyDownstream + "；ADS 列已无下游");

        // ---------- 成本：分区文件清单 + 裁剪谓词 ----------
        List<CostReport.DataFile> files = List.of(
                new CostReport.DataFile("part=2024-05-30/a.parquet", "2024-05-30", 1_000, 900 * MB),
                new CostReport.DataFile("part=2024-06-01/a.parquet", "2024-06-01", 1_000, 1_000 * MB),
                new CostReport.DataFile("part=2024-06-02/a.parquet", "2024-06-02", 500, 60 * MB),
                new CostReport.DataFile("part=2024-06-02/b.parquet", "2024-06-02", 500, 60 * MB),
                new CostReport.DataFile("part=2024-06-02/c.parquet", "2024-06-02", 500, 60 * MB),
                new CostReport.DataFile("part=2024-06-03/a.parquet", "2024-06-03", 2_000, 1_200 * MB));
        CostReport cost = CostReport.build(files, List.of("2024-06-02", "2024-06-03"),
                gate.commits(), gate.rejections());
        System.out.print(cost.renderScreen());

        long expectedBefore = (900 + 1_000 + 60 + 60 + 60 + 1_200) * MB;
        long expectedAfter = (60 + 60 + 60 + 1_200) * MB;

        // G) 成本数字与输入一致
        check(pass, cost.scanBytesBefore() == expectedBefore && cost.scanBytesAfter() == expectedAfter
                        && cost.storageBytes() == expectedBefore && cost.smallFilePartitions() == 1
                        && cost.totalPartitions() == 4
                        && Math.abs(cost.scanSavedRatio() - 0.5793) < 0.001
                        && cost.scanBytesByPartition().equals(Map.of(
                                "2024-05-30", 900 * MB, "2024-06-01", 1_000 * MB,
                                "2024-06-02", 180 * MB, "2024-06-03", 1_200 * MB)),
                "成本数字与输入一致：裁剪前 " + CostReport.human(cost.scanBytesBefore()) + " → 裁剪后 "
                        + CostReport.human(cost.scanBytesAfter()) + "（省 "
                        + String.format("%.1f%%", cost.scanSavedRatio() * 100) + "）；"
                        + cost.smallFilePartitions() + "/" + cost.totalPartitions() + " 个分区是小文件分区（06-02 三个 60MB 小文件）");

        // H) Prometheus 文本语法自检：4 族 / 6 样本行 / 标签带引号 / 先声明后出样本
        String prometheus = cost.renderPrometheus();
        System.out.print(prometheus);
        List<String> lines = prometheus.lines().filter(line -> !line.isBlank()).toList();
        List<String> samples = lines.stream().filter(line -> !line.startsWith("#")).toList();
        boolean familiesDeclared = CostReport.families().stream()
                .allMatch(family -> declaredBeforeSample(lines, family));
        boolean syntaxOk = samples.stream().allMatch(line -> SAMPLE.matcher(line).matches());
        boolean labelsQuoted = samples.stream().filter(line -> line.contains("{"))
                .allMatch(line -> line.contains("=\"") && line.matches(".*=\\\"[^\"]*\\\"\\}.*"));
        // 样本行数 = 指标序列数：lake_scan_bytes 有 before/after 两个序列（2）+ 3 个无标签指标 = 5
        check(pass, samples.size() == 2 + 3 && familiesDeclared && syntaxOk && labelsQuoted
                        && samples.stream().distinct().count() == samples.size(),
                "Prometheus 文本语法自检：4 个指标族各有且仅有一组 # HELP/#TYPE 且在样本之前，"
                        + samples.size() + " 条样本行（scan_bytes 两个 stage 序列 + 3 个无标签指标）全部匹配语法、"
                        + "标签值带双引号、无重复序列");

        // I) 一屏与指标同源（数值一致）
        String screen = cost.renderScreen();
        long metricBefore = metricValue(samples, "lake_scan_bytes{stage=\"before\"}");
        long metricAfter = metricValue(samples, "lake_scan_bytes{stage=\"after\"}");
        long metricSmall = metricValue(samples, "lake_small_file_partitions");
        long metricFailures = metricValue(samples, "lake_gate_failures_total");
        check(pass, metricBefore == cost.scanBytesBefore() && metricAfter == cost.scanBytesAfter()
                        && metricSmall == cost.smallFilePartitions() && metricFailures == gate.rejections()
                        && screen.contains(CostReport.human(cost.scanBytesBefore()))
                        && screen.contains(CostReport.human(cost.scanBytesAfter()))
                        && screen.contains(String.format("%.1f%%", cost.gatePassRatePct())),
                "一屏与指标同源：lake_scan_bytes{before|after}、lake_small_file_partitions、"
                        + "lake_gate_failures_total 与 CostReport 字段逐一相等（同一对象渲染两处）");

        System.out.printf("ALL PASS: %d/%d%n", pass.get(), total);
        if (pass.get() != total) {
            System.exit(1);
        }
    }

    /** 指标族是否「恰好一组 HELP/TYPE，且都排在首个样本行之前」。 */
    private static boolean declaredBeforeSample(List<String> lines, String family) {
        int help = indexOfPrefix(lines, "# HELP " + family + " ");
        int type = indexOfPrefix(lines, "# TYPE " + family + " ");
        int firstSample = -1;
        for (int i = 0; i < lines.size(); i++) {
            if (lines.get(i).startsWith(family + " ") || lines.get(i).startsWith(family + "{")) {
                firstSample = i;
                break;
            }
        }
        return help >= 0 && type >= 0 && firstSample > help && firstSample > type
                && countPrefix(lines, "# HELP " + family + " ") == 1
                && countPrefix(lines, "# TYPE " + family + " ") == 1;
    }

    private static int indexOfPrefix(List<String> lines, String prefix) {
        for (int i = 0; i < lines.size(); i++) {
            if (lines.get(i).startsWith(prefix)) {
                return i;
            }
        }
        return -1;
    }

    private static int countPrefix(List<String> lines, String prefix) {
        return (int) lines.stream().filter(line -> line.startsWith(prefix)).count();
    }

    /** 从样本行里取出数值部分（`name{...} 123` 或 `name 123`）。 */
    private static long metricValue(List<String> samples, String metric) {
        for (String line : samples) {
            if (line.startsWith(metric + " ") || line.startsWith(metric + "{")) {
                Matcher matcher = Pattern.compile(" (-?[0-9]+)$").matcher(line);
                if (matcher.find()) {
                    return Long.parseLong(matcher.group(1));
                }
            }
        }
        throw new IllegalArgumentException("找不到指标：" + metric);
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
