// languages/java/ph23-lakehouse-orchestration/examples/ex06-orchestration-dag/Dag.java —— 依赖图语义：确定性拓扑序、就绪判断、失败阻塞闭包、重试决策、环检测
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex06 *.java && java -cp /tmp/ph23-ex06 OrchestrationDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：8/8 PASS）
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

/**
 * 编排图（DAG）：只管**依赖语义**，不管执行——执行由 {@link Orchestrator} 负责。
 *
 * 本类要回答四个问题（全部确定性，可复盘）：
 *   ① 执行顺序是什么 —— {@link #topoOrder()}：Kahn 算法 + 「同层按 id 升序」打破平局；
 *   ② 现在谁能跑 —— {@link #ready(Set, Set)}：所有上游成功、自己未运行、且不在失败阻塞闭包内；
 *   ③ 失败会拖住谁 —— {@link #blocked(Set)}：失败任务的**全部下游**（直接 + 间接）；
 *   ④ 失败的这条任务该不该再试 —— {@link #onFailure(String)}：重试未耗尽 → RETRY，耗尽 → FAIL 并阻塞下游。
 *
 * 为什么「同层按 id 排序」值得写进算法：编排器每秒可能调度数百任务，顺序不稳定会让
 * 「昨天为什么慢」无法复盘；按 id 升序是成本最低的确定性来源（3.6）。
 */
public final class Dag {

    /** 失败任务的处置：还能重试（重新入队），或重试耗尽（标记失败并阻塞下游）。 */
    public enum FailureAction { RETRY, FAIL }

    private final Map<String, TaskNode> nodes;
    /** 依赖方向：上游 → 下游集合（用于计算失败传播闭包）。 */
    private final Map<String, Set<String>> downstream = new TreeMap<>();
    /** 每个任务已失败的次数（onFailure 的记账）。 */
    private final Map<String, Integer> failures = new HashMap<>();

    public Dag(List<TaskNode> taskNodes) {
        Map<String, TaskNode> byId = new TreeMap<>();
        for (TaskNode node : taskNodes) {
            TaskNode previous = byId.put(node.id(), node);
            if (previous != null) {
                throw new IllegalArgumentException("任务 id 重复：" + node.id());
            }
        }
        for (TaskNode node : byId.values()) {
            for (String dep : node.deps()) {
                if (!byId.containsKey(dep)) {
                    throw new IllegalArgumentException("任务 " + node.id() + " 依赖不存在的任务：" + dep);
                }
            }
        }
        this.nodes = byId;
        for (TaskNode node : byId.values()) {
            downstream.computeIfAbsent(node.id(), key -> new TreeSet<>());
            for (String dep : node.deps()) {
                downstream.computeIfAbsent(dep, key -> new TreeSet<>()).add(node.id());
            }
        }
    }

    /** 按 id 升序的全部任务（稳定的遍历入口）。 */
    public List<TaskNode> tasks() {
        return new ArrayList<>(nodes.values());
    }

    public TaskNode node(String id) {
        TaskNode node = nodes.get(id);
        if (node == null) {
            throw new IllegalArgumentException("未知任务：" + id);
        }
        return node;
    }

    /**
     * 确定性拓扑序：Kahn 算法，但「所有入度为 0 的节点」里**永远先取 id 最小者**。
     * 环存在时返回已排出的部分序列——配合 {@link #hasCycle()} 使用，不会静默给出错的顺序。
     */
    public List<String> topoOrder() {
        Map<String, Integer> indegree = new TreeMap<>();
        for (TaskNode node : nodes.values()) {
            indegree.put(node.id(), node.deps().size());
        }
        // 候选集：入度为 0 的任务，按 id 升序（TreeSet 同时给出去重与确定性）
        TreeSet<String> ready = new TreeSet<>();
        indegree.forEach((id, degree) -> {
            if (degree == 0) {
                ready.add(id);
            }
        });

        List<String> order = new ArrayList<>();
        while (!ready.isEmpty()) {
            String id = ready.pollFirst();   // 关键：同层按 id 升序
            order.add(id);
            for (String next : downstream.getOrDefault(id, Set.of())) {
                int degree = indegree.merge(next, -1, Integer::sum);
                if (degree == 0) {
                    ready.add(next);
                }
            }
        }
        return order;
    }

    /** 环检测：拓扑序排不完所有节点 ⇔ 存在环（依赖不可能被满足）。 */
    public boolean hasCycle() {
        return topoOrder().size() != nodes.size();
    }

    /**
     * 就绪判断：一个任务能跑，当且仅当
     *   ① 它所有 deps 都在 success 里；② 它自己不在 running 里；③ 它不在失败阻塞闭包内。
     * 条件 ① 是「上游**全部**成功」——「部分上游成功就跑」等于用了半份数据（3.6）。
     */
    public List<String> ready(Set<String> success, Set<String> running) {
        Set<String> failed = failureSet();
        Set<String> blocked = blocked(failed);
        List<String> result = new ArrayList<>();
        for (TaskNode node : nodes.values()) {
            if (success.contains(node.id()) || running.contains(node.id()) || blocked.contains(node.id())) {
                continue;
            }
            if (success.containsAll(node.deps())) {
                result.add(node.id());
            }
        }
        return result;
    }

    /**
     * 失败阻塞闭包：给定失败集合，返回它们的**全部下游**（直接 + 间接），不含失败任务自身。
     * 编排器用它在失败发生后显式暴露「哪些任务被拖住了」——跳过下游会产出静默缺口（3.6）。
     */
    public Set<String> blocked(Set<String> failed) {
        Set<String> reached = new LinkedHashSet<>(failed);
        Deque<String> queue = new ArrayDeque<>(new TreeSet<>(failed));
        while (!queue.isEmpty()) {
            String id = queue.pollFirst();
            for (String next : downstream.getOrDefault(id, Set.of())) {
                if (reached.add(next)) {
                    queue.addLast(next);
                }
            }
        }
        reached.removeAll(failed);   // 阻塞集合只含下游，失败任务本身不算「被阻塞」
        return reached;
    }

    /**
     * 失败处置：记录一次失败并回答「重试还是标记失败」。
     * 语义固定为「最多重试 retries 次」（即最多 retries+1 次尝试）：
     *   已失败次数 <= retries → RETRY；否则 → FAIL（此后该任务的全部下游进入阻塞闭包）。
     */
    public FailureAction onFailure(String id) {
        TaskNode node = node(id);
        int count = failures.merge(id, 1, Integer::sum);
        return count <= node.retries() ? FailureAction.RETRY : FailureAction.FAIL;
    }

    /** 已失败的任务（重试耗尽后仍失败的）；编排器据此计算阻塞闭包。 */
    public Set<String> failureSet() {
        Set<String> failed = new TreeSet<>();
        for (Map.Entry<String, Integer> entry : failures.entrySet()) {
            int count = entry.getValue();
            if (count > node(entry.getKey()).retries()) {
                failed.add(entry.getKey());
            }
        }
        return failed;
    }

    /** 已失败次数（用于断言重试计数）。 */
    public int failureCount(String id) {
        return failures.getOrDefault(id, 0);
    }

    /** 稳定渲染：`id(deps=...|retries=n)` 按 id 升序。 */
    public String renderGraph() {
        StringBuilder sb = new StringBuilder();
        for (TaskNode node : nodes.values()) {
            if (sb.length() > 0) {
                sb.append(" | ");
            }
            sb.append(node.id()).append("(deps=").append(node.deps()).append(",retries=").append(node.retries())
                    .append(')');
        }
        return sb.toString();
    }

    /** 按拓扑序渲染成 `a -> b -> c`，用于一屏输出。 */
    public String renderTopoOrder() {
        return String.join(" -> ", topoOrder());
    }

    /** 下游邻接表的有序视图（影响分析/断言用）。 */
    public Map<String, Set<String>> downstreamView() {
        Map<String, Set<String>> view = new TreeMap<>();
        downstream.forEach((id, next) -> view.put(id, new TreeSet<>(next)));
        return view;
    }

}
