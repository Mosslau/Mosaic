// exercises/sol-03-dag-backfill/Sol03Demo.java —— 练习 3 验收入口：确定性拓扑序 + 就绪/重试/失败阻塞 + 幂等回填与断点续跑
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-sol03 *.java && java -cp /tmp/ph23-sol03 Sol03Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.PriorityQueue;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

/**
 * 对应 23-lakehouse-orchestration.md 3.6（数据编排 DAG）、3.7（幂等回填）、4.4 与第 7 章练习 3（sol-03）。
 * 断言是编排与回填四条纪律的可执行形式：
 * ① 拓扑序确定（同层按 id 排序，可复盘）；② 失败耗尽重试后「阻塞」下游而不是「跳过」；
 * ③ 回填 = 依赖闭包 + 分区整体覆盖（重复回填结果一致）；④ 断点续跑只补缺口、非法范围被拒。
 */
public final class Sol03Demo {

    private static int passed = 0;
    private static int total = 0;

    public static void main(String[] args) {
        // ---- 1) 拓扑序确定 + 依赖先行 ----
        Dag dag = sampleDag();
        List<String> first = dag.topoOrder();
        List<String> second = dag.topoOrder();
        boolean depsFirst = true;
        for (int i = 0; i < first.size(); i++) {
            String task = first.get(i);
            List<String> before = first.subList(0, i);
            depsFirst &= before.containsAll(dag.task(task).deps());
        }
        check(first.equals(second)
                        && first.equals(List.of("ods_dim", "ods_load", "dwd_fact", "dws_dau", "ads_board"))
                        && depsFirst,
                "拓扑序确定且依赖先行：" + first + "（两次运行逐项相同）");

        boolean cycleRejected = false;
        String cycleMessage = "";
        try {
            new Dag(List.of(
                    new TaskNode("a", List.of("c"), 2),
                    new TaskNode("b", List.of("a"), 2),
                    new TaskNode("c", List.of("b"), 2))).topoOrder();
        } catch (IllegalStateException e) {
            cycleRejected = true;
            cycleMessage = e.getMessage();
        }
        check(cycleRejected && cycleMessage.contains("环"),
                "有环 DAG 被拒：" + cycleMessage);

        // ---- 2) 就绪判断：上游全部成功才就绪 ----
        Orchestrator orchestrator = new Orchestrator(dag);
        Set<String> success = new TreeSet<>();
        check(orchestrator.ready(success).equals(Set.of("ods_dim", "ods_load")),
                "就绪判断：无上游依赖的 ods_dim/ods_load 就绪，其余等待");
        success.add("ods_load");
        check(orchestrator.ready(success).equals(Set.of("ods_dim", "dwd_fact"))
                        && !orchestrator.ready(Set.of("ods_dim", "ods_load")).contains("ads_board"),
                "就绪判断：上游全部成功才就绪，dws_dau 未成功时 ads_board 不就绪（不跑「半份数据」）");

        // ---- 3) 失败阻塞下游（不是跳过）+ 重试上限 ----
        Orchestrator failing = new Orchestrator(sampleDag());
        failing.fail("ods_load");
        Checkpoint checkpoint = failing.process(taskId -> !"ods_load".equals(taskId));

        Orchestrator successRun = new Orchestrator(sampleDag());
        Checkpoint successCheckpoint = successRun.process(taskId -> true);

        check(checkpoint.attempts("ods_load") == 3
                        && checkpoint.attempts("dwd_fact") == 0
                        && checkpoint.attempts("dws_dau") == 0
                        && checkpoint.attempts("ads_board") == 0,
                "重试上限生效：ods_load 恰好尝试 3 次（1 次 + 2 次重试）后停止，下游一次都没跑");

        check(checkpoint.blocked().equals(Set.of("dwd_fact", "dws_dau", "ads_board"))
                        && checkpoint.failed().equals(Set.of("ods_load"))
                        && checkpoint.succeeded().equals(Set.of("ods_dim")),
                "失败耗尽后阻塞下游而非跳过：blocked=" + checkpoint.blocked() + "，无关任务 ods_dim 照常成功");

        Set<String> reported = new TreeSet<>(checkpoint.states().keySet());
        check(reported.containsAll(List.of("ods_load", "dwd_fact", "dws_dau", "ads_board"))
                        && "BLOCKED".equals(checkpoint.states().get("dws_dau"))
                        && "SUCCESS".equals(successCheckpoint.states().get("dws_dau")),
                "阻塞状态显式暴露在状态里（不是「成功」）：" + checkpoint.states());

        // ---- 4) 回填 = 依赖闭包（下游重算），且不含无关表 ----
        BackfillPlanner planner = new BackfillPlanner(sampleDag().dependencies());
        BackfillPlan plan = planner.plan("dwd_fact", List.of("2024-06-01", "2024-06-02"));
        check(plan.tables().equals(List.of("dwd_fact", "dws_dau", "ads_board"))
                        && plan.partitionsOf("dwd_fact").equals(List.of("2024-06-01", "2024-06-02"))
                        && plan.partitionsOf("ads_board").equals(List.of("2024-06-01", "2024-06-02")),
                "回填闭包覆盖全部下游：" + plan.tables() + "（每表同分区）");

        check(!plan.tables().contains("ods_load")
                        && !plan.tables().contains("ods_dim")
                        && !plan.table("ods_load").isPresent()
                        && plan.size() == 6,
                "闭包不含无关表：ods_load/ods_dim 不在计划内，计划共 " + plan.size() + " 个分区任务");

        boolean badRange = false;
        String badRangeMessage = "";
        try {
            planner.plan("dwd_fact", List.of("2024-06-03", "2024-06-01"));
        } catch (IllegalArgumentException e) {
            badRange = true;
            badRangeMessage = e.getMessage();
        }
        boolean emptyRange = false;
        try {
            planner.plan("dwd_fact", List.of());
        } catch (IllegalArgumentException e) {
            emptyRange = true;
        }
        check(badRange && emptyRange && badRangeMessage.contains("非法"),
                "非法范围被拒：" + badRangeMessage + "；空分区列表同样被拒");

        // ---- 5) 幂等回填：重复回填结果一致 ----
        PartitionStore store = new PartitionStore();
        BackfillPreset preset = BackfillPreset.of(plan, "上游修数");
        BackfillRun run1 = preset.run(store, Set.of());
        String beforeRerun = store.snapshot("dws_dau", "2024-06-01");
        // 第二次带着「第一次的覆盖集合」再跑：分区整体覆盖 → 全部跳过，结果与第一次完全一致。
        BackfillRun run2 = preset.run(store, run1.covered());

        check(run2.executed().isEmpty()
                        && new LinkedHashSet<>(run2.skipped()).equals(new LinkedHashSet<>(run1.executed()))
                        && run1.covered().equals(run2.covered())
                        && beforeRerun.equals(store.snapshot("dws_dau", "2024-06-01")),
                "幂等回填：第二次运行 0 次执行、" + run2.skipped().size() + " 个分区跳过，覆盖集合与内容一致");

        check(store.contentEquals(plan, "上游修数")
                        && run1.covered().size() == plan.size()
                        && store.reason("ads_board", "2024-06-02").equals("上游修数"),
                "分区整体覆盖且原因留痕：每次写入记录 reason（同分区重跑结果一致）");

        // ---- 6) 断点续跑只补缺口 ----
        BackfillPlan wide = planner.plan("ods_load", List.of("2024-06-01", "2024-06-02", "2024-06-03"));
        PartitionStore interruptedStore = new PartitionStore();
        BackfillPreset widePreset = BackfillPreset.of(wide, "规则变更");
        // 中断场景：只完成了前 5 个分区任务，剩下的必须补跑（而不是重跑全部）。
        Set<String> coveredBeforeInterrupt = new LinkedHashSet<>();
        for (BackfillTask planned : wide.tasks()) {
            if (coveredBeforeInterrupt.size() < 5) {
                BackfillTask task = new BackfillTask(planned.table(), planned.partition(), "规则变更");
                coveredBeforeInterrupt.add(task.key());
                interruptedStore.overwrite(task);
            }
        }
        BackfillRun resumed = widePreset.run(interruptedStore, coveredBeforeInterrupt);

        check(new LinkedHashSet<>(resumed.skipped()).equals(coveredBeforeInterrupt)
                        && resumed.executed().size() == wide.size() - coveredBeforeInterrupt.size()
                        && Collections.disjoint(resumed.executed(), resumed.skipped())
                        && resumed.executed().size() + resumed.skipped().size() == wide.size(),
                "断点续跑只补缺口：已覆盖 " + resumed.skipped().size() + " 个跳过，补跑 "
                        + resumed.executed().size() + " 个，合计等于计划 " + wide.size());

        check(resumed.covered().size() == wide.size()
                        && interruptedStore.contentEquals(wide, "规则变更")
                        && new LinkedHashSet<>(run1.covered()).equals(new LinkedHashSet<>(run2.covered())),
                "断点续跑后覆盖集合完整：" + resumed.covered().size() + "/" + wide.size()
                        + " 个分区任务全部有内容，重复运行覆盖集合不变");

        System.out.println("DAG 拓扑序: " + first);
        System.out.println("失败运行: " + checkpoint);
        System.out.println("回填闭包: " + plan.tables() + " / " + plan.size() + " 个分区任务");
        System.out.println("ALL PASS: " + passed + "/" + total);
        if (passed != total) {
            System.exit(1);
        }
    }

    /** 一条 ODS → DWD → DWS → ADS 主链，外加一个与本链无关的 ods_dim。 */
    private static Dag sampleDag() {
        return new Dag(List.of(
                new TaskNode("ads_board", List.of("dws_dau"), 2),
                new TaskNode("dws_dau", List.of("dwd_fact"), 2),
                new TaskNode("dwd_fact", List.of("ods_load"), 2),
                new TaskNode("ods_dim", List.of(), 1),
                new TaskNode("ods_load", List.of(), 2)));
    }

    /** DAG 任务节点：id + 上游依赖 + 重试上限（不含首次尝试）。 */
    public record TaskNode(String id, List<String> deps, int retries) {

        public TaskNode {
            if (id == null || id.isBlank()) {
                throw new IllegalArgumentException("任务 id 不能为空");
            }
            if (retries < 0) {
                throw new IllegalArgumentException("重试上限不能为负：" + id);
            }
            deps = List.copyOf(deps);
        }

        public int maxAttempts() {
            return retries + 1;
        }
    }

    /** 有向无环图：确定性拓扑序（Kahn + 同层按 id 排序）。 */
    public static final class Dag {

        private final Map<String, TaskNode> tasks = new TreeMap<>();

        public Dag(List<TaskNode> nodes) {
            for (TaskNode node : nodes) {
                if (tasks.put(node.id(), node) != null) {
                    throw new IllegalArgumentException("任务 id 重复：" + node.id());
                }
            }
            for (TaskNode node : tasks.values()) {
                for (String dep : node.deps()) {
                    if (!tasks.containsKey(dep)) {
                        throw new IllegalArgumentException("未知上游依赖：" + node.id() + " → " + dep);
                    }
                }
            }
        }

        public TaskNode task(String id) {
            TaskNode node = tasks.get(id);
            if (node == null) {
                throw new IllegalArgumentException("未知任务：" + id);
            }
            return node;
        }

        public Set<String> ids() {
            return new LinkedHashSet<>(tasks.keySet());
        }

        /** 表的依赖关系（下游 → 上游），用于回填闭包传播。 */
        public Map<String, Set<String>> dependencies() {
            Map<String, Set<String>> deps = new TreeMap<>();
            for (TaskNode node : tasks.values()) {
                deps.put(node.id(), new TreeSet<>(node.deps()));
            }
            return deps;
        }

        /**
         * 确定性拓扑序：可用任务放进按 id 排序的优先队列，因此同层永远按 id 出队。
         * 顺序不稳定会让「昨天为什么慢」无法复盘，所以确定性是编排器的硬要求。
         */
        public List<String> topoOrder() {
            Map<String, Integer> indegree = new TreeMap<>();
            Map<String, List<String>> downstream = new TreeMap<>();
            for (TaskNode node : tasks.values()) {
                indegree.putIfAbsent(node.id(), 0);
                for (String dep : node.deps()) {
                    indegree.merge(node.id(), 1, Integer::sum);
                    downstream.computeIfAbsent(dep, k -> new ArrayList<>()).add(node.id());
                }
            }
            PriorityQueue<String> ready = new PriorityQueue<>();
            indegree.forEach((id, degree) -> {
                if (degree == 0) {
                    ready.add(id);
                }
            });
            List<String> order = new ArrayList<>();
            while (!ready.isEmpty()) {
                String id = ready.poll();
                order.add(id);
                for (String next : downstream.getOrDefault(id, List.of())) {
                    if (indegree.merge(next, -1, Integer::sum) == 0) {
                        ready.add(next);
                    }
                }
            }
            if (order.size() != tasks.size()) {
                throw new IllegalStateException("DAG 存在环，无法拓扑排序：已完成 "
                        + order.size() + "/" + tasks.size() + " 个任务");
            }
            return order;
        }
    }

    /** 一次运行的检查点：状态 / 尝试次数 / 成功 / 失败 / 阻塞。 */
    public record Checkpoint(Map<String, String> states, Map<String, Integer> attempts,
                             Set<String> succeeded, Set<String> failed, Set<String> blocked) {

        public Checkpoint {
            states = Collections.unmodifiableMap(new TreeMap<>(states));
            attempts = Collections.unmodifiableMap(new TreeMap<>(attempts));
            succeeded = Collections.unmodifiableSet(new TreeSet<>(succeeded));
            failed = Collections.unmodifiableSet(new TreeSet<>(failed));
            blocked = Collections.unmodifiableSet(new TreeSet<>(blocked));
        }

        public int attempts(String task) {
            return attempts.getOrDefault(task, 0);
        }

        @Override
        public String toString() {
            return "success=" + succeeded + " failed=" + failed + " blocked=" + blocked;
        }
    }

    /**
     * 确定性内存编排器：就绪 = 上游全部 SUCCESS；失败 = 重试耗尽后标记 FAILED 并阻塞全部下游。
     * 阻塞的任务状态是 BLOCKED（显式暴露），绝不是 SUCCESS——静默缺口比显式失败贵得多。
     */
    public static final class Orchestrator {

        private final Dag dag;
        private final Map<String, Integer> attempts = new TreeMap<>();
        private final Set<String> succeeded = new TreeSet<>();
        private final Set<String> failed = new TreeSet<>();
        private final Set<String> permanentFailures = new TreeSet<>();

        public Orchestrator(Dag dag) {
            this.dag = dag;
            for (String id : dag.ids()) {
                attempts.put(id, 0);
            }
        }

        /** 让某任务在后续运行中永远失败（模拟坏数据的确定性故障）。 */
        public void fail(String taskId) {
            permanentFailures.add(taskId);
        }

        /** 当前就绪任务：自身未跑、上游全部成功。 */
        public Set<String> ready(Set<String> success) {
            Set<String> ready = new TreeSet<>();
            for (String id : dag.ids()) {
                if (success.contains(id) || failed.contains(id) || isBlocked(id)) {
                    continue;
                }
                if (success.containsAll(dag.task(id).deps())) {
                    ready.add(id);
                }
            }
            return ready;
        }

        /**
         * 跑到没有就绪任务为止。任务执行结果由 {@code shouldSucceed} 决定（确定性，不掷骰子），
         * 失败且重试未耗尽时重新入队，耗尽后标记 FAILED 并让其下游保持 BLOCKED。
         */
        public Checkpoint process(java.util.function.Predicate<String> shouldSucceed) {
            Set<String> success = new TreeSet<>(succeeded);
            while (true) {
                Set<String> ready = ready(success);
                if (ready.isEmpty()) {
                    break;
                }
                for (String id : ready) {
                    TaskNode node = dag.task(id);
                    boolean ok = false;
                    for (int attempt = 0; attempt < node.maxAttempts(); attempt++) {
                        attempts.merge(id, 1, Integer::sum);
                        if (shouldSucceed.test(id) && !permanentFailures.contains(id)) {
                            ok = true;
                            break;
                        }
                    }
                    if (ok) {
                        succeeded.add(id);
                        success.add(id);
                    } else {
                        failed.add(id);
                    }
                }
            }
            return new Checkpoint(states(), attempts, succeeded, failed, blocked());
        }

        public Map<String, String> states() {
            Map<String, String> states = new TreeMap<>();
            for (String id : dag.ids()) {
                if (succeeded.contains(id)) {
                    states.put(id, "SUCCESS");
                } else if (failed.contains(id)) {
                    states.put(id, "FAILED");
                } else if (isBlocked(id)) {
                    states.put(id, "BLOCKED");
                } else {
                    states.put(id, "PENDING");
                }
            }
            return states;
        }

        public Set<String> blocked() {
            Set<String> blocked = new TreeSet<>();
            for (String id : dag.ids()) {
                if (isBlocked(id)) {
                    blocked.add(id);
                }
            }
            return blocked;
        }

        /** 阻塞 = 自身未成功，且某个上游失败（传递闭包上）。 */
        private boolean isBlocked(String id) {
            if (succeeded.contains(id) || failed.contains(id)) {
                return false;
            }
            return dag.task(id).deps().stream().anyMatch(dep ->
                    failed.contains(dep) || isBlocked(dep));
        }
    }

    /** 回填计划：一组 (表, 分区) 任务，按拓扑序排列。 */
    public record BackfillPlan(List<String> tables, Map<String, List<String>> partitionByTable,
                               String reason) {

        public BackfillPlan {
            tables = List.copyOf(tables);
            Map<String, List<String>> copy = new TreeMap<>();
            partitionByTable.forEach((table, partitions) -> copy.put(table, List.copyOf(partitions)));
            partitionByTable = Collections.unmodifiableMap(copy);
        }

        public Optional<List<String>> table(String name) {
            return Optional.ofNullable(partitionByTable.get(name));
        }

        public List<String> partitionsOf(String table) {
            return partitionByTable.getOrDefault(table, List.of());
        }

        /** 计划内的分区任务总数。 */
        public int size() {
            return partitionByTable.values().stream().mapToInt(List::size).sum();
        }

        /** 扁平化成 (表, 分区) 执行序列，顺序确定。 */
        public List<BackfillTask> tasks() {
            List<BackfillTask> tasks = new ArrayList<>();
            for (String table : tables) {
                for (String partition : partitionsOf(table)) {
                    tasks.add(new BackfillTask(table, partition, reason));
                }
            }
            return tasks;
        }
    }

    /** 回填任务：表 + 分区 + 原因（留痕）。 */
    public record BackfillTask(String table, String partition, String reason) {

        public String key() {
            return table + "@" + partition;
        }
    }

    /**
     * 回填计划器：给定起始表与分区，沿「依赖图」向下游传播闭包。
     * 只重算上游而不重算下游，就会新旧口径混用——所以传播闭包是回填的正确性条件。
     */
    public static final class BackfillPlanner {

        private final Map<String, Set<String>> dependencies;

        public BackfillPlanner(Map<String, Set<String>> dependencies) {
            this.dependencies = new TreeMap<>();
            dependencies.forEach((table, deps) -> this.dependencies.put(table, new TreeSet<>(deps)));
        }

        /** @param start 上游被重算的表 @param partitions 需要重算的分区（升序，不允许为空） */
        public BackfillPlan plan(String start, List<String> partitions) {
            if (!dependencies.containsKey(start)) {
                throw new IllegalArgumentException("未知表：" + start);
            }
            if (partitions == null || partitions.isEmpty()) {
                throw new IllegalArgumentException("非法范围：分区列表不能为空");
            }
            if (new TreeSet<>(partitions).size() != partitions.size()) {
                throw new IllegalArgumentException("非法范围：分区列表有重复");
            }
            for (int i = 1; i < partitions.size(); i++) {
                if (partitions.get(i - 1).compareTo(partitions.get(i)) >= 0) {
                    throw new IllegalArgumentException("非法范围：分区必须严格升序且无重复（"
                            + partitions.get(i - 1) + " → " + partitions.get(i) + "）");
                }
            }

            Set<String> closure = new TreeSet<>();
            collect(start, closure);
            List<String> ordered = new ArrayList<>(new BackfillPlanner(dependencies).topoOrder());
            ordered.retainAll(closure);
            Map<String, List<String>> byTable = new TreeMap<>();
            for (String table : ordered) {
                byTable.put(table, List.copyOf(partitions));
            }
            return new BackfillPlan(ordered, byTable, "回填 " + start + " " + partitions);
        }

        /** 下游闭包：谁依赖我，我就要跟着重算（传递）。 */
        private void collect(String table, Set<String> closure) {
            closure.add(table);
            for (Map.Entry<String, Set<String>> entry : dependencies.entrySet()) {
                if (entry.getValue().contains(table) && !closure.contains(entry.getKey())) {
                    collect(entry.getKey(), closure);
                }
            }
        }

        /** 与 DAG 相同的确定性拓扑序，保证计划本身可复盘。 */
        public List<String> topoOrder() {
            Map<String, Integer> indegree = new TreeMap<>();
            Map<String, List<String>> downstream = new TreeMap<>();
            for (Map.Entry<String, Set<String>> entry : dependencies.entrySet()) {
                indegree.putIfAbsent(entry.getKey(), 0);
                for (String dep : entry.getValue()) {
                    indegree.merge(entry.getKey(), 1, Integer::sum);
                    downstream.computeIfAbsent(dep, k -> new ArrayList<>()).add(entry.getKey());
                }
            }
            PriorityQueue<String> ready = new PriorityQueue<>();
            indegree.forEach((table, degree) -> {
                if (degree == 0) {
                    ready.add(table);
                }
            });
            List<String> order = new ArrayList<>();
            while (!ready.isEmpty()) {
                String table = ready.poll();
                order.add(table);
                for (String next : downstream.getOrDefault(table, List.of())) {
                    if (indegree.merge(next, -1, Integer::sum) == 0) {
                        ready.add(next);
                    }
                }
            }
            if (order.size() != dependencies.size()) {
                throw new IllegalStateException("依赖图存在环，无法为回填排序");
            }
            return order;
        }
    }

    /**
     * 分区存储：写入是「整个分区覆盖」而不是追加。
     * 于是重跑同一分区结果与第一次完全一致（幂等），不需要主键 upsert 也删得掉源里消失的行。
     */
    public static final class PartitionStore {

        private final Map<String, String> content = new TreeMap<>();
        private final Map<String, String> reasons = new TreeMap<>();

        /** 整体覆盖一个分区，并记录本次回填原因。 */
        public void overwrite(BackfillTask task) {
            content.put(task.key(), task.reason());
            reasons.put(task.key(), task.reason());
        }

        public boolean contains(String table, String partition) {
            return content.containsKey(table + "@" + partition);
        }

        public String snapshot(String table, String partition) {
            return content.get(table + "@" + partition);
        }

        public String reason(String table, String partition) {
            return reasons.get(table + "@" + partition);
        }


        public boolean contentEquals(BackfillPlan plan, String reason) {
            return plan.tasks().stream().allMatch(task ->
                    reason.equals(snapshot(task.table(), task.partition())));
        }
    }

    /** 回填计划 + 原因：run(store, alreadyCovered) 幂等，已覆盖的分区直接跳过。 */
    public record BackfillPreset(BackfillPlan plan, String reason) {

        public static BackfillPreset of(BackfillPlan plan, String reason) {
            return new BackfillPreset(plan, reason);
        }

        /**
         * 过滤计划里的分区任务并**用本次预设的 reason 重写**（原因属于「这一次回填」，不属于计划）。
         * {@code alreadyCovered} 里的 (表@分区) 不重复执行（断点续跑），其余分区整体覆盖写入。
         */
        public BackfillRun run(PartitionStore store, Set<String> alreadyCovered) {
            List<String> executed = new ArrayList<>();
            List<String> skipped = new ArrayList<>();
            for (BackfillTask planned : plan.tasks()) {
                BackfillTask task = new BackfillTask(planned.table(), planned.partition(), reason);
                if (alreadyCovered.contains(planned.key())) {
                    skipped.add(task.key());
                    continue;
                }
                store.overwrite(task);
                executed.add(task.key());
            }
            return new BackfillRun(executed, skipped);
        }
    }

    /** 一次回填运行的结果：真正执行的分区、跳过的分区、覆盖全集。 */
    public record BackfillRun(List<String> executed, List<String> skipped) {

        public BackfillRun {
            executed = List.copyOf(executed);
            skipped = List.copyOf(skipped);
        }

        public Set<String> covered() {
            Set<String> all = new TreeSet<>(skipped);
            all.addAll(executed);
            return all;
        }
    }

    private static void check(boolean ok, String label) {
        total++;
        if (ok) {
            passed++;
        }
        System.out.println((ok ? "PASS " : "FAIL ") + label);
    }
}
