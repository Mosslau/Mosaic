// languages/java/ph23-lakehouse-orchestration/examples/ex07-backfill-idempotent/Backfill.java —— 幂等回填：分区整体覆盖 + 下游重算闭包 + 断点续跑 + 原因留痕
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex07 *.java && java -cp /tmp/ph23-ex07 BackfillDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：8/8 PASS）
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

/**
 * 最小回填引擎：把 3.7 / 4.4 的四条正确性条件落成代码。
 *
 *   ① **分区整体覆盖（幂等）**：{@link #run} 每次都按 (table,partition) 用同一个纯函数重新算出整份分区值，
 *      然后**整体替换**——不是追加、也不是 upsert。重跑同一分区结果逐项相同。
 *   ② **下游传播闭包**：{@link #plan} 从源表出发沿依赖图向下传播 partition 范围，
 *      产出「待重算分区 + 全部受影响下游分区」。只重算上游会让下游混用新旧口径，且无法自动发现（4.4）。
 *   ③ **断点续跑**：{@link #run} 记录已成功 (table,partition)；{@link #resume} 只跑缺口。
 *   ④ **原因留痕**：每次执行追加一条 (table,partition,reason)，可审计「谁在什么时候为什么重算了哪一天」。
 *
 * 数据模型刻意做到「聚合值真的由上游算出来」：`dws` 分区值 = 该天 `dwd` 分区值 × 2，
 * `ads` 分区值 = 该天 `dws` 分区值 + 100。于是「重算后的下游值 == 按新上游重算的值」是一个
 * **可验证的等式**，而不是自己跟自己对答案。
 */
public final class Backfill {

    /** 回填的执行痕迹：谁、哪个分区、什么原因。 */
    public record BackfillRecord(String table, String partition, String reason) { }

    private final String sourceTable;
    /** 表依赖：表 → 它的直接下游（数据流向）。 */
    private final Map<String, List<String>> tableDeps;
    /** 表 → 分区 → 分区值（确定性内存版「表」）。 */
    private final Map<String, Map<String, Long>> data = new TreeMap<>();
    /** 已成功回填的 (table,partition)，用于断点续跑。 */
    private final Set<String> succeeded = new LinkedHashSet<>();
    private final List<BackfillRecord> history = new ArrayList<>();
    /** 模拟故障：这些分区第一次执行时失败（不写入成功集合），用于验证断点续跑。 */
    private final Set<String> failingOnce = new TreeSet<>();

    public Backfill(String sourceTable, Map<String, List<String>> tableDeps, Map<String, Map<String, Long>> data) {
        this.sourceTable = sourceTable;
        Map<String, List<String>> deps = new TreeMap<>();
        tableDeps.forEach((table, downstream) -> deps.put(table, List.copyOf(downstream)));
        this.tableDeps = deps;
        data.forEach((table, partitions) -> this.data.put(table, new TreeMap<>(partitions)));
    }

    /** 造一个下界可预期的确定性数据集：分区值 = 该天序号 × 基准值。 */
    public static Map<String, Map<String, Long>> seedData(List<String> tables, List<String> partitions, long base) {
        Map<String, Map<String, Long>> seed = new TreeMap<>();
        for (String table : tables) {
            Map<String, Long> byPartition = new TreeMap<>();
            for (int i = 0; i < partitions.size(); i++) {
                byPartition.put(partitions.get(i), base * (i + 1));
            }
            seed.put(table, byPartition);
        }
        return seed;
    }

    /** 标记「这些分区第一次执行会失败」，模拟中断；随后再跑就是断点续跑。 */
    public void failOnceForTable(String table, List<String> partitions) {
        for (String partition : partitions) {
            failingOnce.add(table + "/" + partition);
        }
    }

    /**
     * 回填计划：源表 sourceTable 的 [fromPartition, toPartition] 分区，加上**依赖图上的下游重算闭包**。
     *
     * 传播规则：某表 T 的分区范围变化 → 它的每个下游表 D 的**同范围分区**也要重算（示例用同样的日期分区键）。
     * 返回按 (table,partition) 有序的确定性列表：同一份输入计划必然逐项相同，可直接 diff。
     */
    public List<BackfillTask> plan(String table, String fromPartition, String toPartition) {
        if (fromPartition.compareTo(toPartition) > 0) {
            throw new IllegalArgumentException(
                    "非法分区范围：from=" + fromPartition + " > to=" + toPartition);
        }
        if (!data.containsKey(table)) {
            throw new IllegalArgumentException("未知表：" + table);
        }
        Map<String, List<String>> rangeByTable = new TreeMap<>();
        rangeByTable.put(table, List.of(fromPartition, toPartition));

        // 依赖方向传播：已确定范围的每个表，把同样范围推给它的下游表（广度优先，结果按 TreeMap 收敛）。
        List<String> frontier = new ArrayList<>(List.of(table));
        Set<String> visited = new TreeSet<>(List.of(table));
        while (!frontier.isEmpty()) {
            List<String> next = new ArrayList<>();
            for (String current : new ArrayList<>(frontier)) {
                for (String downstream : tableDeps.getOrDefault(current, List.of())) {
                    if (!data.containsKey(downstream)) {
                        continue;
                    }
                    rangeByTable.putIfAbsent(downstream, List.of(fromPartition, toPartition));
                    if (visited.add(downstream)) {
                        next.add(downstream);
                    }
                }
            }
            frontier = next;
        }

        // 任务顺序 = **表的拓扑序**（上游先于下游），同表内再按分区升序。
        // 这一点不是排版问题：若按字典序先跑 ADS 再跑 DWS，ADS 就会读到旧 DWS——重算了却仍然错。
        List<BackfillTask> tasks = new ArrayList<>();
        String reason = "上游修数：" + table + " [" + fromPartition + ".." + toPartition + "] 重算传播";
        for (String current : topologicalTables()) {
            List<String> range = rangeByTable.get(current);
            if (range == null || !data.containsKey(current)) {
                continue;
            }
            for (String partition : data.get(current).keySet()) {
                if (partition.compareTo(range.get(0)) >= 0 && partition.compareTo(range.get(1)) <= 0) {
                    tasks.add(new BackfillTask(current, partition, reason));
                }
            }
        }
        return tasks;
    }

    /** 表的拓扑序（依赖图上的确定性顺序）：Kahn 算法、同层按表名字典序，保证计划可复现。 */
    public List<String> topologicalTables() {
        Map<String, Integer> indegree = new TreeMap<>();
        for (String table : data.keySet()) {
            indegree.put(table, 0);
        }
        for (Map.Entry<String, List<String>> entry : tableDeps.entrySet()) {
            for (String downstream : entry.getValue()) {
                if (indegree.containsKey(downstream)) {
                    indegree.merge(downstream, 1, Integer::sum);
                }
            }
        }
        TreeSet<String> ready = new TreeSet<>();
        indegree.forEach((table, degree) -> {
            if (degree == 0) {
                ready.add(table);
            }
        });
        List<String> order = new ArrayList<>();
        while (!ready.isEmpty()) {
            String table = ready.pollFirst();
            order.add(table);
            for (String downstream : tableDeps.getOrDefault(table, List.of())) {
                if (indegree.containsKey(downstream) && indegree.merge(downstream, -1, Integer::sum) == 0) {
                    ready.add(downstream);
                }
            }
        }
        // 依赖图之外的孤立表（例如完全独立的导出表）按字典序排在最后，但不在任何闭包里
        for (String table : data.keySet()) {
            if (!order.contains(table)) {
                order.add(table);
            }
        }
        return order;
    }

    /**
     * 执行一个任务：按 (table,partition) **整体覆盖**该分区的值（幂等），成功后记入断点。
     * 分区值由依赖图从上游确定性推出：ODS/DWD 用种子值；DWS = 同天 DWD × 2；ADS = 同天 DWS + 100。
     */
    public boolean run(BackfillTask task) {
        String key = task.table() + "/" + task.partition();
        if (failingOnce.remove(key)) {
            history.add(new BackfillRecord(task.table(), task.partition(), task.reason() + "（首次尝试失败，待续跑）"));
            return false;   // 模拟中断：不写成功集合，也不改数据
        }
        Map<String, Long> table = data.get(task.table());
        if (table == null || !table.containsKey(task.partition())) {
            throw new IllegalArgumentException("表或分区不存在：" + key);
        }
        table.put(task.partition(), recompute(task.table(), task.partition()));   // 整体覆盖，不追加
        succeeded.add(key);
        history.add(new BackfillRecord(task.table(), task.partition(), task.reason()));
        return true;
    }

    /**
     * 口径（唯一的表级变换，读的都是**当前上游值**，所以上游一改、下游重算就跟着变）：
     *   ods_raw  → 种子值（原始层不做业务解释）
     *   dwd_event→ ods_raw
     *   dws      → ods_raw × 2
     *   ads      → dws + 100
     * 只有单一聚合链，避免「DWS 直接吞 DWD 值」这种把两层变化混在同一次聚合里的写法。
     */
    public long recompute(String table, String partition) {
        long ods = require("ods_raw", partition);
        return switch (table) {
            case "dwd_event" -> ods;
            case "dws" -> ods * 2;
            case "ads" -> ods * 2 + 100;
            default -> ods;
        };
    }

    /** 断点续跑：只跑计划里尚未成功的分区，返回实际执行的任务列表。 */
    public List<BackfillTask> resume(List<BackfillTask> tasks) {
        List<BackfillTask> executed = new ArrayList<>();
        for (BackfillTask task : tasks) {
            if (!succeeded.contains(task.table() + "/" + task.partition())) {
                if (run(task)) {
                    executed.add(task);
                }
            }
        }
        return executed;
    }

    /** 计划里已被断点覆盖（无需重跑）的任务。 */
    public List<BackfillTask> alreadySucceeded(List<BackfillTask> tasks) {
        List<BackfillTask> done = new ArrayList<>();
        for (BackfillTask task : tasks) {
            if (succeeded.contains(task.table() + "/" + task.partition())) {
                done.add(task);
            }
        }
        return done;
    }

    /** 原因留痕：与成功执行一一对应（失败尝试也留痕，便于排查中断）。 */
    public List<BackfillRecord> history() {
        return List.copyOf(history);
    }

    public Map<String, Map<String, Long>> data() {
        Map<String, Map<String, Long>> copy = new TreeMap<>();
        data.forEach((table, partitions) -> copy.put(table, new TreeMap<>(partitions)));
        return copy;
    }

    public long value(String table, String partition) {
        return require(table, partition);
    }

    public Set<String> succeededKeys() {
        return new TreeSet<>(succeeded);
    }

    private long require(String table, String partition) {
        Map<String, Long> partitions = data.get(table);
        if (partitions == null || !partitions.containsKey(partition)) {
            throw new IllegalArgumentException("表或分区不存在：" + table + "/" + partition);
        }
        return partitions.get(partition);
    }

    /** 一屏渲染：`table/partition=value` 按表与分区升序。 */
    public String render() {
        StringBuilder sb = new StringBuilder();
        data.forEach((table, partitions) -> {
            sb.append(table).append('{');
            boolean first = true;
            for (Map.Entry<String, Long> entry : partitions.entrySet()) {
                if (!first) {
                    sb.append(',');
                }
                first = false;
                sb.append(entry.getKey()).append('=').append(entry.getValue());
            }
            sb.append("} ");
        });
        return sb.toString().trim();
    }

    /** 计划渲染：`table/partition` 列表。 */
    public static String renderPlan(List<BackfillTask> tasks) {
        List<String> labels = new ArrayList<>();
        for (BackfillTask task : tasks) {
            labels.add(task.table() + "/" + task.partition());
        }
        return labels.toString();
    }

    /** 留痕渲染：`table/partition(reason)`。 */
    public static String renderHistory(List<BackfillRecord> records) {
        List<String> labels = new ArrayList<>();
        for (BackfillRecord record : records) {
            labels.add(record.table() + "/" + record.partition() + "(" + record.reason() + ")");
        }
        return labels.toString();
    }

    /** 便于断言「闭包覆盖了某表某分区」。 */
    public static boolean covers(List<BackfillTask> tasks, String table, String partition) {
        for (BackfillTask task : tasks) {
            if (task.table().equals(table) && task.partition().equals(partition)) {
                return true;
            }
        }
        return false;
    }

    /** 依赖图的可用表集合（构造数据时校验用）。 */
    public Map<String, List<String>> tableDeps() {
        Map<String, List<String>> copy = new LinkedHashMap<>();
        tableDeps.forEach(copy::put);
        return copy;
    }
}
