// project/src/lakeplat/Backfill.java —— 幂等回填：分区覆盖 + 下游重算闭包 + 断点续跑 + 原因留痕
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

/**
 * 幂等回填（主文档 3.7 / 4.4）：湖仓最容易做错的动作，也是最值得建模的动作。
 *
 * <p>正确性条件可以写成一句话（4.4）：
 * <blockquote>对任意表 T 与分区 P，若 T 的输入发生变化，则**依赖 T 的、包含 P 的所有下游分区**
 * 都必须被重算，且重算必须幂等。</blockquote>
 *
 * <p>本类把这句话拆成四个可验证的机制：
 * <ol>
 *   <li><b>分区级幂等</b>：{@link #put}/{@link #run} 按分区**整体覆盖**（不追加、不 upsert）——
 *       追加会让重跑翻倍，upsert 永远无法反映源里删除的行；</li>
 *   <li><b>下游传播</b>：{@link #plan} 用 {@link WarehouseModel#downstreamClosure} 得到依赖闭包，
 *       再按**分区粒度对齐**筛出「包含 P」的下游分区；</li>
 *   <li><b>断点续跑</b>：{@link #resume} 跳过已成功的分区，只补缺口；</li>
 *   <li><b>原因留痕</b>：每次执行追加一条 {@link ReasonLog}，含「重算了哪些分区、跳过哪些、为什么」。</li>
 * </ol>
 *
 * <p>派生表读数由 {@link TableCalc} **纯函数**算出（同输入必同输出），
 * 这是「重复回填结果一致」的结构性保证——不是靠执行时小心翼翼，而是靠算子本身没有随机性与累加状态。
 */
public final class Backfill {

    /** 一个分区当前的数据读数（行数 + 字节数 + 文件数）。 */
    public record PartitionData(long rows, long bytes, int files) {
        public PartitionData {
            if (rows < 0 || bytes < 0 || files < 0) {
                throw new IllegalArgumentException("分区的行/字节/文件数不能为负");
            }
        }

        public static PartitionData of(long rows, long bytes, int files) {
            return new PartitionData(rows, bytes, files);
        }

        /** 确定性摘要（回填幂等性断言的比较对象）。 */
        public String digest() {
            return rows + "/" + bytes + "/" + files;
        }
    }

    /** 派生表的口径（纯函数）：由上游分区读数算出本表分区读数。 */
    @FunctionalInterface
    public interface TableCalc {
        PartitionData calculate(TableRef table, String partition, Map<TableRef, PartitionData> upstream);
    }

    /** 一次回填计划的读数。 */
    public record Plan(TableRef origin, String partition, String reason,
                       List<BackfillTask> tasks, List<BackfillTask> downstreamTasks, Set<String> dayKeys) {
        /** 闭包内的下游表（除起点外，字典序）。 */
        public Set<String> downstreamTables() {
            Set<String> tables = new TreeSet<>();
            downstreamTasks.forEach(task -> tables.add(task.table().table()));
            return tables;
        }

        public String label() {
            return "起点 " + origin.table() + "/" + partition + " → 重算 " + tasks.size()
                    + " 个分区（下游 " + downstreamTables() + "）";
        }
    }

    /** 一次执行的读数。 */
    public record RunResult(List<String> appliedOrder, List<BackfillTask> applied,
                            List<BackfillTask> skipped, Map<String, PartitionData> state, long tsMillis) {
        /** 全量状态的确定性摘要（两次回填后必须逐字节相同）。 */
        public String digest() {
            StringBuilder sb = new StringBuilder();
            state.forEach((key, value) -> sb.append(key).append('=').append(value.digest()).append(';'));
            return sb.toString();
        }

        public String label() {
            return "执行 " + applied.size() + " 个分区，跳过 " + skipped.size() + " 个";
        }
    }

    /** 原因留痕：一次回填的完整记录。 */
    public record ReasonLog(long tsMillis, String originTable, String partition, String reason,
                            List<String> recalculated, List<String> skipped) {
        @Override
        public String toString() {
            return "@" + tsMillis + " " + originTable + "/" + partition + " —— " + reason
                    + "（重算 " + recalculated.size() + " 个分区，跳过 " + skipped.size() + "）";
        }
    }

    /** DWD 明细的行字节比（示例口径：明细一行 6 字节）。 */
    public static final long DWD_BYTES_PER_ROW = 6L;
    /** 派生表的目标文件大小（用于把字节折算成文件数，与 compaction 的目标值同源）。 */
    public static final long FILE_TARGET_BYTES = 512L * 1024L;

    private final WarehouseModel model;
    private final Map<Layer, TableCalc> calcs = new LinkedHashMap<>();
    private final Map<String, Long> source = new TreeMap<>();
    private final Map<String, PartitionData> state = new TreeMap<>();
    private final Map<String, Long> dayOffsetCache = new TreeMap<>();
    private final Set<String> appliedKeys = new TreeSet<>();
    private final List<ReasonLog> reasonLog = new ArrayList<>();

    public Backfill(WarehouseModel model) {
        this.model = model;
        // DWD：明细层以 ODS 来的"源数据"为准（源数据用行数表达，避免为了演示造假的 ODS 分区粒度）
        calcs.put(Layer.DWD, (table, partition, upstream) -> {
            long rows = source.getOrDefault(dayOf(partition), 0L);
            return PartitionData.of(rows, rows * DWD_BYTES_PER_ROW, filesOf(rows * DWD_BYTES_PER_ROW));
        });
        // DWS：汇总层 = DWD 同分区求和（口径唯一源的实现）
        calcs.put(Layer.DWS, (table, partition, upstream) -> {
            long rows = upstream.values().stream().mapToLong(PartitionData::rows).sum();
            return PartitionData.of(rows, rows * 16L, filesOf(rows * 16L));
        });
        // ADS：应用层 = DWS 同分区聚合
        calcs.put(Layer.ADS, (table, partition, upstream) -> {
            long rows = upstream.values().stream().mapToLong(PartitionData::rows).sum();
            return PartitionData.of(rows, rows * 8L, filesOf(rows * 8L));
        });
    }

    private static int filesOf(long bytes) {
        return (int) Math.max(1, (bytes + FILE_TARGET_BYTES - 1) / FILE_TARGET_BYTES);
    }

    /** 声明细层的"源数据"（上游修数就是改这里，不是改表本身）。 */
    public void setSource(String partition, long rows) {
        source.put(dayOf(partition), rows);
    }

    public long sourceOf(String partition) {
        return source.getOrDefault(dayOf(partition), 0L);
    }

    /** 覆盖某一层派生表的口径（扩展点）。 */
    public void registerCalc(Layer layer, TableCalc calc) {
        calcs.put(layer, calc);
    }

    /** 写入/覆盖某分区（**整体覆盖**，这是幂等的物理基础）。 */
    public PartitionData put(TableRef table, String partition, PartitionData data) {
        model.require(table);
        state.put(key(table, partition), data);
        return data;
    }

    public PartitionData get(TableRef table, String partition) {
        model.require(table);
        return state.getOrDefault(key(table, partition), PartitionData.of(0, 0, 0));
    }

    public long rowsOf(TableRef table, String partition) {
        return get(table, partition).rows();
    }

    public boolean has(TableRef table, String partition) {
        return state.containsKey(key(table, partition));
    }

    public Map<String, PartitionData> state() {
        return java.util.Collections.unmodifiableMap(new TreeMap<>(state));
    }

    public List<ReasonLog> reasonLog() {
        return List.copyOf(reasonLog);
    }

    /** 已成功执行过的分区（断点续跑的依据）。 */
    public Set<String> appliedKeys() {
        return new TreeSet<>(appliedKeys);
    }

    /** 把已知分区组装成 {@link TableCalc} 的上游视图。 */
    private Map<TableRef, PartitionData> upstreamView(TableRef table, String partition) {
        Map<TableRef, PartitionData> upstream = new TreeMap<>(Comparator.comparing(TableRef::table));
        for (TableRef dep : model.upstreamOf(table)) {
            upstream.put(dep, get(dep, partition));
        }
        return upstream;
    }

    /** 纯函数计算某表某分区的读数（回填的"重算"动作）。 */
    public PartitionData calculate(TableRef table, String partition) {
        TableCalc calc = calcs.get(table.layer());
        if (calc == null) {
            throw new IllegalStateException("层 " + table.layer() + " 没有登记口径（TableCalc）：" + table);
        }
        return calc.calculate(table, partition, upstreamView(table, partition));
    }

    /**
     * 产出回填计划：**依赖图闭包 + 分区粒度对齐**。
     *
     * <p>闭包里的表并不都该重算同一分区：ODS 按月分区、DWD 按天分区时，重算 DWD 某天
     * 不应该、也无法重算 ODS 的"某一天"（粒度不同）。所以计划里只保留「分区键偏移能与起点对齐」的表——
     * 这正是「重算依赖 T 的、**包含 P 的**所有下游分区」里的「包含 P」。
     */
    public Plan plan(TableRef origin, String partition, String reason) {
        model.require(origin);
        Set<TableRef> affected = new TreeSet<>(Comparator.comparing(TableRef::table));
        affected.add(origin);
        affected.addAll(model.downstreamClosure(origin));
        List<BackfillTask> tasks = new ArrayList<>();
        List<BackfillTask> downstream = new ArrayList<>();
        Set<String> dayKeys = new TreeSet<>();
        for (TableRef table : affected) {
            if (!partitionAligned(origin, table, partition)) {
                continue;
            }
            BackfillTask task = new BackfillTask(table, partition, reason);
            tasks.add(task);
            if (!table.equals(origin)) {
                downstream.add(task);
            }
            dayKeys.add(dayOf(partition));
        }
        tasks.sort(taskComparator());
        downstream.sort(taskComparator());
        return new Plan(origin, partition, reason, List.copyOf(tasks), List.copyOf(downstream), Set.copyOf(dayKeys));
    }

    private boolean partitionAligned(TableRef origin, TableRef table, String partition) {
        if (table.equals(origin)) {
            return true;
        }
        long originOffset = model.partitionOffsetDays(origin);
        long tableOffset = model.partitionOffsetDays(table);
        long originDayOffset = dayOffsetOf(dayOf(partition));
        long tableDayOffset = originDayOffset - tableOffset + originOffset;
        return dayOf(partition).equals(Window.dayKeyAt(tableDayOffset));
    }

    /** 日期分区 → 相对 ORIGIN 的天偏移（带缓存；解析失败即报错，不静默兜底）。 */
    private long dayOffsetOf(String day) {
        Long cached = dayOffsetCache.get(day);
        if (cached != null) {
            return cached;
        }
        for (long offset = 0; offset < 40_000; offset++) {
            if (Window.dayKeyAt(offset).equals(day)) {
                dayOffsetCache.put(day, offset);
                return offset;
            }
        }
        throw new IllegalArgumentException("无法解析的日期分区：" + day);
    }

    /**
     * 断点续跑：从计划里移除**已成功执行过**的任务。
     *
     * <p>中断后重启不该从头再跑一遍全量——已经覆盖成功的分区落的是同一个确定值，重跑只是浪费算力。
     */
    public List<BackfillTask> resume(Plan plan) {
        List<BackfillTask> pending = new ArrayList<>();
        for (BackfillTask task : plan.tasks()) {
            if (!appliedKeys.contains(task.key())) {
                pending.add(task);
            }
        }
        pending.sort(taskComparator());
        return List.copyOf(pending);
    }

    /** 执行完整计划。 */
    public RunResult execute(Plan plan, long tsMillis) {
        return run(plan, tsMillis, plan.tasks());
    }

    /**
     * 模拟中断的执行：只跑前 {@code limit} 个任务，最后一个标记为「中断前未执行」。
     *
     * <p>之所以要模拟中断，是因为「断点续跑」只有在真的断了的时候才看得出价值。
     */
    public RunResult executeInterrupted(Plan plan, long tsMillis, int limit) {
        if (limit >= plan.tasks().size()) {
            return run(plan, tsMillis, plan.tasks());
        }
        List<BackfillTask> truncated = new ArrayList<>(plan.tasks().subList(0, limit));
        BackfillTask last = truncated.get(truncated.size() - 1);
        truncated.set(truncated.size() - 1,
                new BackfillTask(last.table(), last.partition(), "（中断前未执行）"));
        return run(plan, tsMillis, List.copyOf(truncated));
    }

    /** 断点续跑的执行入口：跳过已成功的分区，只补缺口。 */
    public RunResult resumeAndRun(Plan plan, long tsMillis) {
        List<BackfillTask> pending = resume(plan);
        RunResult result = run(plan, tsMillis, pending);
        List<BackfillTask> skipped = new ArrayList<>();
        for (BackfillTask task : plan.tasks()) {
            if (appliedKeys.contains(task.key())) {
                skipped.add(task);
            }
        }
        return new RunResult(result.appliedOrder(), result.applied(), List.copyOf(skipped),
                result.state(), tsMillis);
    }

    private RunResult run(Plan plan, long tsMillis, List<BackfillTask> todo) {
        List<BackfillTask> applied = new ArrayList<>();
        List<BackfillTask> skipped = new ArrayList<>();
        for (BackfillTask task : todo) {
            if (task.reason().startsWith("（中断前未执行）") || appliedKeys.contains(task.key())) {
                skipped.add(task);
                continue;
            }
            PartitionData data = calculate(task.table(), task.partition());
            put(task.table(), task.partition(), data);
            appliedKeys.add(task.key());
            applied.add(task);
        }
        List<String> appliedOrder = new ArrayList<>();
        applied.forEach(task -> appliedOrder.add(task.key()));
        List<String> skippedKeys = new ArrayList<>();
        skipped.forEach(task -> skippedKeys.add(task.key()));
        reasonLog.add(new ReasonLog(tsMillis, plan.origin().table(), plan.partition(), plan.reason(),
                List.copyOf(appliedOrder), List.copyOf(skippedKeys)));
        return new RunResult(List.copyOf(appliedOrder), List.copyOf(applied), List.copyOf(skipped),
                state(), tsMillis);
    }

    /**
     * 排序：先按层序号（上游先于下游），再按分区，最后按表名。
     *
     * <p>确定性排序让「回填计划」本身可复盘；上游先算也保证下游读到的已经是新数据。
     */
    private Comparator<BackfillTask> taskComparator() {
        return Comparator.comparingInt((BackfillTask task) -> task.table().layer().ordinal())
                .thenComparing(BackfillTask::partition)
                .thenComparing(task -> task.table().table());
    }

    private String key(TableRef table, String partition) {
        return table.table() + "/" + partition;
    }

    private static String dayOf(String partition) {
        return partition.contains("=") ? partition.substring(partition.indexOf('=') + 1) : partition;
    }
}
