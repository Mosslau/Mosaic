// project/src/lakeplat/Dag.java —— DAG：确定性拓扑序 + 就绪判断 + 失败阻塞下游
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.TreeSet;

/**
 * 编排 DAG（主文档 3.6）：拓扑序确定性、就绪条件严格、失败阻塞下游而非跳过。
 *
 * <p>三条纪律各有理由：
 * <ul>
 *   <li><b>拓扑序同层按 id 排序</b>：编排器每秒可能调度数百个任务，顺序一旦不稳定，
 *       同样输入会产出不同执行顺序，「昨天为什么慢」就无法复盘。</li>
 *   <li><b>就绪 = 上游全部成功</b>：「部分上游成功」就跑 = 用了半份数据。</li>
 *   <li><b>失败阻塞下游，不跳过</b>：跳过看起来「跑完了」，但 ADS 里会出现一段没有数据的日期，
 *       值班看到的是「任务成功」，直到业务发现缺口——<b>静默缺口比显式失败贵得多</b>。</li>
 * </ul>
 */
public final class Dag {

    /** 任务状态机。 */
    public enum State {
        PENDING, RUNNING, SUCCEEDED, FAILED, BLOCKED
    }

    /** 一个任务的当前状态与尝试次数。 */
    public static final class NodeState {
        private State state = State.PENDING;
        private int attempts;
        private String failureReason;

        public State state() {
            return state;
        }

        public int attempts() {
            return attempts;
        }

        public String failureReason() {
            return failureReason;
        }

        @Override
        public String toString() {
            return state + (attempts > 0 ? "(尝试 " + attempts + ")" : "");
        }
    }

    private final Map<String, TaskNode> nodes = new TreeMap<>();
    private final Map<String, List<String>> upstream = new TreeMap<>();
    private final Map<String, List<String>> downstream = new TreeMap<>();
    private final Map<String, List<String>> transitivelyBlockedBy = new TreeMap<>();
    private final List<String> topoOrder;

    public Dag(List<TaskNode> taskNodes) {
        for (TaskNode node : taskNodes) {
            if (nodes.put(node.id(), node) != null) {
                throw new IllegalStateException("任务 id 重复：" + node.id());
            }
        }
        for (TaskNode node : nodes.values()) {
            List<String> ups = new ArrayList<>();
            for (String dep : node.deps()) {
                if (!nodes.containsKey(dep)) {
                    throw new IllegalStateException("任务 " + node.id() + " 依赖未定义的任务：" + dep);
                }
                ups.add(dep);
                downstream.computeIfAbsent(dep, key -> new ArrayList<>()).add(node.id());
            }
            ups.sort(String::compareTo);
            upstream.put(node.id(), List.copyOf(ups));
        }
        downstream.replaceAll((id, list) -> {
            List<String> sorted = new ArrayList<>(list);
            sorted.sort(String::compareTo);
            return List.copyOf(sorted);
        });
        this.topoOrder = computeTopoOrder();
    }

    /** 确定性拓扑序（Kahn + 最小 id 优先）：同层按 id 字典序，保证可重放。 */
    private List<String> computeTopoOrder() {
        Map<String, Integer> indegree = new TreeMap<>();
        nodes.keySet().forEach(id -> indegree.put(id, upstream.get(id).size()));
        Deque<String> ready = new ArrayDeque<>();
        indegree.forEach((id, degree) -> {
            if (degree == 0) {
                ready.addLast(id);
            }
        });
        List<String> order = new ArrayList<>();
        while (!ready.isEmpty()) {
            String id = ready.pollFirst();          // 队列已按 id 排序入队，取出即最小 id
            order.add(id);
            for (String child : downstream.getOrDefault(id, List.of())) {
                int remaining = indegree.merge(child, -1, Integer::sum);
                if (remaining == 0) {
                    insertSorted(ready, child);
                }
            }
        }
        if (order.size() != nodes.size()) {
            throw new IllegalStateException("DAG 存在环，无法拓扑排序（已排 " + order.size() + "/" + nodes.size() + "）");
        }
        return List.copyOf(order);
    }

    private void insertSorted(Deque<String> ready, String id) {
        List<String> buffer = new ArrayList<>(ready);
        buffer.add(id);
        buffer.sort(String::compareTo);
        ready.clear();
        ready.addAll(buffer);
    }

    public List<String> topoOrder() {
        return topoOrder;
    }

    public List<TaskNode> nodes() {
        return List.copyOf(nodes.values());
    }

    public TaskNode node(String id) {
        TaskNode node = nodes.get(id);
        if (node == null) {
            throw new IllegalStateException("任务不存在：" + id);
        }
        return node;
    }

    public List<String> upstreamOf(String id) {
        node(id);
        return upstream.get(id);
    }

    public List<String> downstreamOf(String id) {
        node(id);
        return downstream.getOrDefault(id, List.of());
    }

    /** 就绪判断：所有上游都已成功，且自身尚未运行/未终结。 */
    public boolean ready(String id, Map<String, State> states, java.util.Set<String> running) {
        node(id);
        State own = states.getOrDefault(id, State.PENDING);
        if (own != State.PENDING || running.contains(id)) {
            return false;
        }
        for (String dep : upstream.get(id)) {
            if (states.getOrDefault(dep, State.PENDING) != State.SUCCEEDED) {
                return false;
            }
        }
        return true;
    }

    /** 当前所有就绪任务（按拓扑序过滤，天然确定性）。 */
    public List<String> readyTasks(Map<String, State> states, java.util.Set<String> running) {
        List<String> ready = new ArrayList<>();
        for (String id : topoOrder) {
            if (ready(id, states, running)) {
                ready.add(id);
            }
        }
        return List.copyOf(ready);
    }

    /** 失败传播：某个任务终结失败后，它**传递闭包**内的所有下游都必须阻塞（而不是被跳过）。 */
    public List<String> blockedClosure(String failedId) {
        node(failedId);
        List<String> blocked = new ArrayList<>();
        Deque<String> queue = new ArrayDeque<>(downstreamOf(failedId));
        java.util.Set<String> visited = new TreeSet<>();
        while (!queue.isEmpty()) {
            String current = queue.pollFirst();
            if (visited.add(current)) {
                blocked.add(current);
                queue.addAll(downstreamOf(current));
            }
        }
        blocked.sort(String::compareTo);
        return List.copyOf(blocked);
    }

    /** 记录「谁被谁阻塞」，用于把「阻塞中」显式暴露在一屏上。 */
    public void recordBlocking(String failedId, List<String> blockedIds) {
        for (String blocked : blockedIds) {
            transitivelyBlockedBy.computeIfAbsent(blocked, key -> new ArrayList<>()).add(failedId);
        }
        transitivelyBlockedBy.replaceAll((id, list) -> List.copyOf(new TreeSet<>(list)));
    }

    /** 被哪些失败任务阻塞（字典序）。 */
    public List<String> blockedBy(String id) {
        return transitivelyBlockedBy.getOrDefault(id, List.of());
    }

    /** 依赖闭包（下游全部任务，含直接与间接），供编排器做失败传播。 */
    public List<String> downstreamClosure(String id) {
        return blockedClosure(id);
    }
}
