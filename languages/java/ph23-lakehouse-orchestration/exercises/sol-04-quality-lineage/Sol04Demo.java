// exercises/sol-04-quality-lineage/Sol04Demo.java —— 练习 4 验收入口：五类质量门禁 + fail-closed 提交 + 列级血缘闭包
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-sol04 *.java && java -cp /tmp/ph23-sol04 Sol04Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

/**
 * 对应 23-lakehouse-orchestration.md 3.8（质量、血缘与成本）与第 7 章练习 4（sol-04）。
 * 断言是「质量兜底」两条纪律的可执行形式：
 * ① 五类门禁（非空/唯一/量程/行数波动/鲜度）各自能拦下对应坏数据，任一失败即 fail-closed 拒绝提交；
 * ② 列级血缘能追到 ODS、能给出改上游列的下游影响集合，且门禁明细可读（含失败原因与具体列/数值）。
 */
public final class Sol04Demo {

    private static int passed = 0;
    private static int total = 0;

    public static void main(String[] args) {
        // ---- 0) 列级血缘：输出列 ← 输入列（列级而非表级，才做得了影响分析）----
        LineageGraph lineage = new LineageGraph(Map.of(
                "ods_instance_event", Map.of(
                        "instance_id", Set.of(),
                        "event_time", Set.of(),
                        "event_type", Set.of()),
                "dwd_instance_fact", Map.of(
                        "instance_id", Set.of("ods_instance_event.instance_id"),
                        "event_time", Set.of("ods_instance_event.event_time"),
                        "event_type", Set.of("ods_instance_event.event_type"),
                        "ds", Set.of("ods_instance_event.event_time")),
                "dws_daily_active", Map.of(
                        "ds", Set.of("ods_instance_event.event_time"),
                        "dau", Set.of("dwd_instance_fact.instance_id", "dwd_instance_fact.event_type")),
                "ads_instance_dashboard", Map.of(
                        "stat_date", Set.of("dws_daily_active.ds"),
                        "active_cnt", Set.of("dws_daily_active.dau"))));

        check(lineage.upstreamClosure("dws_daily_active", "dau").equals(Set.of(
                        "dwd_instance_fact.instance_id",
                        "dwd_instance_fact.event_type",
                        "ods_instance_event.instance_id",
                        "ods_instance_event.event_type")),
                "列级血缘上游闭包：dws_daily_active.dau 可追到 ODS 的 instance_id/event_type");

        boolean reachesOds = lineage.upstreamClosure("ads_instance_dashboard", "active_cnt").stream()
                .anyMatch(column -> column.startsWith("ods_instance_event."));
        check(reachesOds
                        && lineage.upstreamClosure("ads_instance_dashboard", "active_cnt").equals(Set.of(
                                "dws_daily_active.dau",
                                "dwd_instance_fact.instance_id",
                                "dwd_instance_fact.event_type",
                                "ods_instance_event.instance_id",
                                "ods_instance_event.event_type")),
                "血缘跨三层传递：ADS.active_cnt → DWS.dau → DWD → ODS（闭包完整）");

        check(lineage.downstream("ods_instance_event", "instance_id").equals(Set.of(
                        "dwd_instance_fact.instance_id",
                        "dws_daily_active.dau",
                        "ads_instance_dashboard.active_cnt"))
                        && lineage.downstream("ods_instance_event", "event_time").equals(Set.of(
                                "dwd_instance_fact.ds",
                                "dwd_instance_fact.event_time",
                                "dws_daily_active.ds",
                                "ads_instance_dashboard.stat_date")),
                "下游影响集合正确：改 ODS.instance_id → 3 列；改 ODS.event_time → 4 列（含 dwd.ds 退化列）");

        // ---- 1) 五类门禁：各自能拦下对应坏数据 ----
        // 每类门禁都被一份「只犯这一类错」的坏数据打到：
        //   重复键(唯一) / null(非空) / 负延迟(量程) / 行数塌方(行数波动) / 迟到(鲜度)
        List<Map<String, Object>> badRows = new ArrayList<>();
        badRows.add(row("u1", "2024-06-01", 100.0, 1_718_000_000_000L));
        badRows.add(row("u1", "2024-06-01", 120.0, 1_718_000_000_000L));
        badRows.add(row(null, "2024-06-01", 90.0, 1_718_000_000_000L));
        badRows.add(row("u4", "2024-06-01", -5.0, 1_718_000_000_000L));

        List<Gate> gates = List.of(
                new NotNullGate(List.of("user_id", "ds", "latency_ms")),
                new UniqueGate(List.of("user_id")),
                new RangeGate("latency_ms", 0.0, 10_000.0),
                new RowCountGate(3, 0.20),
                new FreshnessGate("ingest_ms", 2 * 60 * 60 * 1000L));

        QualityReport report = new QualityChecker().check(badRows, gates, 1_718_003_600_000L);
        Map<String, GateResult> byName = report.byName();

        check(byName.keySet().equals(Set.of("not_null", "unique", "range", "row_count", "freshness"))
                        && report.failedNames().equals(Set.of("not_null", "unique", "range", "row_count"))
                        && byName.get("freshness").passed()
                        && !report.passed(),
                "坏数据被四类门禁同时拦下（一次跑出全部问题）：" + report.failedNames());

        Map<String, Object> nullRow = row(null, null, 10.0, 1_718_000_000_000L);
        GateResult nullResult = new NotNullGate(List.of("user_id", "ds", "latency_ms"))
                .check(List.of(row("u8", "2024-06-01", 10.0, 1_718_000_000_000L), nullRow), 0L);
        check(!nullResult.passed()
                        && nullResult.reason().contains("user_id")
                        && nullResult.reason().contains("ds")
                        && nullResult.reason().contains("1/2"),
                "非空门禁：报出具体空列与行数（" + nullResult.reason() + "）");

        GateResult uniqueResult = new UniqueGate(List.of("user_id"))
                .check(List.of(row("u1", "d1", 1.0, 0L), row("u1", "d1", 2.0, 0L), row("u2", "d1", 3.0, 0L)), 0L);
        check(!uniqueResult.passed()
                        && uniqueResult.reason().contains("1 个重复键")
                        && uniqueResult.reason().contains("|u1")
                        && uniqueResult.reason().contains("总行数 3"),
                "唯一门禁：报出重复键值与总行数（" + uniqueResult.reason() + "）");

        GateResult rangeResult = new RangeGate("latency_ms", 0.0, 100.0)
                .check(List.of(row("u1", "d1", 150.0, 0L), row("u2", "d1", 50.0, 0L)), 0L);
        check(!rangeResult.passed()
                        && rangeResult.reason().contains("latency_ms")
                        && rangeResult.reason().contains("150.0")
                        && rangeResult.reason().contains("100.0"),
                "量程门禁：报出越界列、最小/最大值与允许范围（" + rangeResult.reason() + "）");

        GateResult rowCountResult = new RowCountGate(1000, 0.20)
                .check(List.of(row("u1", "d1", 1.0, 0L), row("u2", "d1", 2.0, 0L)), 0L);
        check(!rowCountResult.passed()
                        && rowCountResult.reason().contains("2")
                        && rowCountResult.reason().contains("1000")
                        && rowCountResult.reason().contains("波动"),
                "行数波动门禁：实际行数偏离基线超过阈值即失败（" + rowCountResult.reason() + "）");

        GateResult freshnessResult = new FreshnessGate("ingest_ms", 3_600_000L)
                .check(List.of(row("u1", "d1", 1.0, 0L)), 5_000_000_000L);
        check(!freshnessResult.passed()
                        && freshnessResult.reason().contains("lag=")
                        && freshnessResult.reason().contains("sla="),
                "鲜度门禁：报出滞后与 SLA（" + freshnessResult.reason() + "）");

        // ---- 2) fail-closed：门禁失败即拒绝提交（表停在上一个快照）----
        List<Map<String, Object>> staleRows = List.of(
                row("u1", "2024-06-01", 100.0, 1_717_999_000_000L),
                row("u2", "2024-06-01", 120.0, 1_717_999_000_000L));
        QualityReport staleReport = new QualityChecker().check(staleRows, gates, 1_718_003_600_000L);

        TableCommitter committer = new TableCommitter();
        CommitOutcome firstAttempt = committer.tryCommit("dws_daily_active", staleRows, staleReport);
        check(!firstAttempt.committed()
                        && firstAttempt.version() == 0
                        && committer.version("dws_daily_active") == 0
                        && committer.lastGood("dws_daily_active").isEmpty()
                        && !firstAttempt.reasons().isEmpty(),
                "门禁失败时提交被拒（fail-closed）：表停在 version 0，坏数据一行都没进去");

        // ---- 3) 全部通过时提交成功 ----
        List<Map<String, Object>> goodRows = List.of(
                row("u1", "2024-06-01", 100.0, 1_718_003_500_000L),
                row("u2", "2024-06-01", 120.0, 1_718_003_500_000L),
                row("u3", "2024-06-01", 90.0, 1_718_003_500_000L));
        QualityReport goodReport = new QualityChecker().check(goodRows, gates, 1_718_003_600_000L);
        CommitOutcome goodAttempt = committer.tryCommit("dws_daily_active", goodRows, goodReport);
        check(goodAttempt.committed()
                        && goodAttempt.version() == 1
                        && committer.version("dws_daily_active") == 1
                        && committer.lastGood("dws_daily_active")
                                .map(rows -> rows.size() == 3)
                                .orElse(false)
                        && goodAttempt.reasons().isEmpty()
                        && goodReport.failedNames().isEmpty(),
                "全部门禁通过时提交成功：version 0 → 1，当前快照 = 3 行（上一快照仍在历史里）");

        Set<String> allowedNames = Set.of("not_null", "unique", "range", "row_count", "freshness");
        Set<String> actualNames = new HashSet<>(goodReport.results().stream()
                .map(GateResult::gate)
                .toList());
        check(actualNames.equals(allowedNames)
                        && goodReport.results().size() == 5
                        && goodReport.results().stream()
                                .allMatch(result -> result.passed() && result.reason().contains(result.gate())),
                "五类门禁齐备且明细可读：" + actualNames);

        check(staleReport.failedNames().equals(Set.of("row_count"))
                        && staleReport.failureSummary().size() == 1
                        && staleReport.failureSummary().get(0).contains("row_count")
                        && staleReport.failureSummary().get(0).contains("基线 3")
                        && firstAttempt.reasons().equals(staleReport.failureSummary())
                        && !firstAttempt.reasons().isEmpty(),
                "门禁明细含失败原因且驱动拒绝：" + firstAttempt.reasons());

        boolean unknownMetric = false;
        try {
            double avg = committer.lastGood("dws_daily_active").orElseThrow().stream()
                    .mapToDouble(row -> ((Number) row.get("latency_ms")).doubleValue())
                    .average()
                    .orElseThrow();
            unknownMetric = avg > 0;
        } catch (RuntimeException e) {
            unknownMetric = false;
        }
        check(unknownMetric && committer.snapshotHistory("dws_daily_active").size() == 1,
                "提交历史只留成功版本：被拒的提交不产生快照（历史长度 1）");

        System.out.println("血缘闭包: " + lineage.upstreamClosure("ads_instance_dashboard", "active_cnt").size()
                + " 列（含 ODS）");
        System.out.println("门禁: " + goodReport.summary());
        System.out.println("提交: " + committer.snapshotHistory("dws_daily_active"));
        System.out.println("ALL PASS: " + passed + "/" + total);
        if (passed != total) {
            System.exit(1);
        }
    }

    /** 构造一行：Map 允许 null 值（非空门禁要用它）。 */
    private static Map<String, Object> row(String userId, String ds, double latencyMs, long ingestMs) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("user_id", userId);
        row.put("ds", ds);
        row.put("latency_ms", latencyMs);
        row.put("ingest_ms", ingestMs);
        return row;
    }

    /** 门禁接口：五类检查共用 (rows, nowMillis) → GateResult。 */
    public sealed interface Gate permits NotNullGate, UniqueGate, RangeGate, RowCountGate, FreshnessGate {

        String name();

        GateResult check(List<Map<String, Object>> rows, long nowMillis);
    }

    /** 门禁结果：通过与否 + 可读原因（失败时必须说清哪一列/什么值/超了什么阈值）。 */
    public record GateResult(String gate, boolean passed, String reason) {

        public static GateResult pass(String gate, String detail) {
            return new GateResult(gate, true, detail);
        }

        public static GateResult fail(String gate, String reason) {
            return new GateResult(gate, false, reason);
        }
    }

    /** 非空门禁：指定列不允许 null/空串。 */
    public record NotNullGate(List<String> columns) implements Gate {

        public NotNullGate {
            columns = List.copyOf(columns);
        }

        @Override
        public String name() {
            return "not_null";
        }

        @Override
        public GateResult check(List<Map<String, Object>> rows, long nowMillis) {
            List<String> badColumns = new ArrayList<>();
            int badRows = 0;
            for (Map<String, Object> row : rows) {
                boolean bad = false;
                for (String column : columns) {
                    if (isBlank(row.get(column)) && !badColumns.contains(column)) {
                        badColumns.add(column);
                    }
                    bad = bad || isBlank(row.get(column));
                }
                if (bad) {
                    badRows++;
                }
            }
            if (badRows > 0) {
                return GateResult.fail(name(), name() + " 失败：" + badRows + "/" + rows.size()
                        + " 行出现空值，列=" + badColumns);
            }
            return GateResult.pass(name(), name() + " 通过：" + rows.size() + " 行、列=" + columns + " 均非空");
        }
    }

    /** 唯一门禁：指定键组合必须唯一。 */
    public record UniqueGate(List<String> keyColumns) implements Gate {

        public UniqueGate {
            keyColumns = List.copyOf(keyColumns);
        }

        @Override
        public String name() {
            return "unique";
        }

        @Override
        public GateResult check(List<Map<String, Object>> rows, long nowMillis) {
            Map<String, Integer> counts = new LinkedHashMap<>();
            for (Map<String, Object> row : rows) {
                StringBuilder key = new StringBuilder();
                for (String column : keyColumns) {
                    key.append('|').append(row.get(column));
                }
                counts.merge(key.toString(), 1, Integer::sum);
            }
            List<String> duplicated = counts.entrySet().stream()
                    .filter(entry -> entry.getValue() > 1)
                    .map(Map.Entry::getKey)
                    .toList();
            if (!duplicated.isEmpty()) {
                return GateResult.fail(name(), name() + " 失败：" + duplicated.size() + " 个重复键（"
                        + duplicated + "），总行数 " + rows.size());
            }
            return GateResult.pass(name(), name() + " 通过：" + rows.size() + " 行，键=" + keyColumns + " 唯一");
        }
    }

    /** 量程门禁：数值列必须落在 [min, max] 内。 */
    public record RangeGate(String column, double min, double max) implements Gate {

        @Override
        public String name() {
            return "range";
        }

        @Override
        public GateResult check(List<Map<String, Object>> rows, long nowMillis) {
            double lowest = Double.POSITIVE_INFINITY;
            double highest = Double.NEGATIVE_INFINITY;
            int violations = 0;
            for (Map<String, Object> row : rows) {
                Object value = row.get(column);
                if (!(value instanceof Number number)) {
                    continue;
                }
                double v = number.doubleValue();
                lowest = Math.min(lowest, v);
                highest = Math.max(highest, v);
                if (v < min || v > max) {
                    violations++;
                }
            }
            if (violations > 0) {
                return GateResult.fail(name(), name() + " 失败：" + column + " 有 " + violations
                        + " 行越界，实际范围=[" + lowest + ", " + highest + "]，允许范围=[" + min + ", " + max + "]");
            }
            return GateResult.pass(name(), name() + " 通过：" + column + " 范围=[" + lowest + ", " + highest
                    + "] ⊆ [" + min + ", " + max + "]");
        }
    }

    /** 行数波动门禁：实际行数相对基线（如昨天）偏离超过容忍比例即失败。 */
    public record RowCountGate(long baseline, double tolerance) implements Gate {

        @Override
        public String name() {
            return "row_count";
        }

        @Override
        public GateResult check(List<Map<String, Object>> rows, long nowMillis) {
            long actual = rows.size();
            double drift = baseline == 0 ? (actual == 0 ? 0.0 : 1.0)
                    : Math.abs(actual - baseline) / (double) baseline;
            if (drift > tolerance) {
                return GateResult.fail(name(), name() + " 失败：行数波动 " + String.format("%.2f", drift)
                        + " 超过阈值 " + String.format("%.2f", tolerance)
                        + "（实际 " + actual + "，基线 " + baseline + "）");
            }
            return GateResult.pass(name(), name() + " 通过：实际 " + actual + " vs 基线 " + baseline
                    + "，波动 " + String.format("%.2f", drift) + " ≤ " + String.format("%.2f", tolerance));
        }
    }

    /** 鲜度门禁：最新数据时间距现在不能超过 SLA。 */
    public record FreshnessGate(String column, long slaMillis) implements Gate {

        @Override
        public String name() {
            return "freshness";
        }

        @Override
        public GateResult check(List<Map<String, Object>> rows, long nowMillis) {
            long newest = Long.MIN_VALUE;
            for (Map<String, Object> row : rows) {
                Object value = row.get(column);
                if (value instanceof Number number) {
                    newest = Math.max(newest, number.longValue());
                }
            }
            long lag = rows.isEmpty() ? Long.MAX_VALUE : nowMillis - newest;
            if (lag > slaMillis) {
                return GateResult.fail(name(), name() + " 失败：数据滞后 lag=" + lag
                        + "ms 超过 sla=" + slaMillis + "ms（最新 " + column + "="
                        + (newest == Long.MIN_VALUE ? "<无>" : newest) + "）");
            }
            return GateResult.pass(name(), name() + " 通过：lag=" + lag + "ms ≤ sla=" + slaMillis + "ms");
        }
    }

    /** 质量报告：五类结果 + 失败集合 + 可读汇总。 */
    public record QualityReport(List<GateResult> results) {

        public QualityReport {
            results = List.copyOf(results);
        }

        public Map<String, GateResult> byName() {
            Map<String, GateResult> byName = new TreeMap<>();
            results.forEach(result -> byName.put(result.gate(), result));
            return byName;
        }

        public Set<String> failedNames() {
            Set<String> failed = new TreeSet<>();
            results.stream().filter(result -> !result.passed()).forEach(result -> failed.add(result.gate()));
            return failed;
        }

        public boolean passed() {
            return results.stream().allMatch(GateResult::passed);
        }

        /** 失败原因的逐条明细（提交被拒时直接回给调用方）。 */
        public List<String> failureSummary() {
            return results.stream().filter(result -> !result.passed()).map(GateResult::reason).toList();
        }

        public String summary() {
            long ok = results.stream().filter(GateResult::passed).count();
            return ok + "/" + results.size() + " 通过"
                    + (failedNames().isEmpty() ? "" : "，失败=" + failedNames());
        }
    }

    /** 门禁执行器：按声明顺序跑完所有门禁（不做短路，好让一次告警把所有问题说清）。 */
    public static final class QualityChecker {

        public QualityReport check(List<Map<String, Object>> rows, List<Gate> gates, long nowMillis) {
            List<GateResult> results = new ArrayList<>();
            for (Gate gate : gates) {
                results.add(gate.check(rows, nowMillis));
            }
            return new QualityReport(results);
        }
    }

    /** 提交结果：是否成功 + 版本号 + 拒绝原因。 */
    public record CommitOutcome(boolean committed, long version, List<String> reasons) {

        public CommitOutcome {
            reasons = List.copyOf(reasons);
        }
    }

    /**
     * 表提交器：门禁是发布的前置条件。任一 FAIL → 拒绝提交，当前快照保持上一个成功版本。
     * 「告警后继续」会让坏数据进表，而下一次的修复成本随时间指数上升。
     */
    public static final class TableCommitter {

        private final Map<String, Long> versions = new HashMap<>();
        private final Map<String, List<Map<String, Object>>> lastGood = new HashMap<>();
        private final Map<String, List<Long>> history = new HashMap<>();

        public CommitOutcome tryCommit(String table, List<Map<String, Object>> rows, QualityReport report) {
            if (!report.passed()) {
                return new CommitOutcome(false, version(table), report.failureSummary());
            }
            long next = version(table) + 1;
            versions.put(table, next);
            lastGood.put(table, List.copyOf(rows));
            history.computeIfAbsent(table, key -> new ArrayList<>()).add(next);
            return new CommitOutcome(true, next, List.of());
        }

        public long version(String table) {
            return versions.getOrDefault(table, 0L);
        }

        public Optional<List<Map<String, Object>>> lastGood(String table) {
            return Optional.ofNullable(lastGood.get(table));
        }

        public List<Long> snapshotHistory(String table) {
            return List.copyOf(history.getOrDefault(table, List.of()));
        }
    }

    /**
     * 列级血缘图：记录「输出列 ← 上游列集合」。列级是变更影响分析与合规追溯的最小单位。
     */
    public static final class LineageGraph {

        private final Map<String, Map<String, Set<String>>> graph = new TreeMap<>();

        public LineageGraph(Map<String, Map<String, Set<String>>> graph) {
            graph.forEach((table, columns) -> {
                Map<String, Set<String>> copy = new TreeMap<>();
                columns.forEach((column, upstream) -> copy.put(column, new TreeSet<>(upstream)));
                this.graph.put(table, Collections.unmodifiableMap(copy));
            });
        }

        public Map<String, Set<String>> columnsOf(String table) {
            return graph.getOrDefault(table, Map.of());
        }

        /** 上游闭包：把「输出列 ← 输入列」一路追到没有上游为止（通常就是 ODS）。 */
        public Set<String> upstreamClosure(String table, String column) {
            Set<String> closure = new TreeSet<>();
            collectUpstream(pair(table, column), closure);
            closure.remove(pair(table, column));
            return closure;
        }

        private void collectUpstream(String pair, Set<String> closure) {
            if (!closure.add(pair)) {
                return;
            }
            for (String upstream : upstreamOf(pair)) {
                collectUpstream(upstream, closure);
            }
        }

        /** 下游影响集合：改这个 (表, 列) 会波及哪些列（含跨表传递）。 */
        public Set<String> downstream(String table, String column) {
            Set<String> affected = new TreeSet<>();
            collectDownstream(pair(table, column), affected);
                affected.remove(pair(table, column));
            return affected;
        }

        private void collectDownstream(String pair, Set<String> affected) {
            if (!affected.add(pair)) {
                return;
            }
            for (Map.Entry<String, Map<String, Set<String>>> tableEntry : graph.entrySet()) {
                for (Map.Entry<String, Set<String>> columnEntry : tableEntry.getValue().entrySet()) {
                    String target = pair(tableEntry.getKey(), columnEntry.getKey());

                    if (columnEntry.getValue().contains(pair)) {
                        collectDownstream(target, affected);
                    }
                }
            }
        }

        public Set<String> upstreamOf(String pair) {
            int dot = pair.indexOf('.');
            if (dot < 0) {
                throw new IllegalArgumentException("列引用必须形如 表.列：" + pair);
            }
            return columnsOf(pair.substring(0, dot)).getOrDefault(pair.substring(dot + 1), Set.of());
        }

        private static String pair(String table, String column) {
            return table + "." + column;
        }
    }

    private static boolean isBlank(Object value) {
        return value == null || (value instanceof CharSequence text && text.toString().isBlank());
    }

    private static void check(boolean ok, String label) {
        total++;
        if (ok) {
            passed++;
        }
        System.out.println((ok ? "PASS " : "FAIL ") + label);
    }
}
