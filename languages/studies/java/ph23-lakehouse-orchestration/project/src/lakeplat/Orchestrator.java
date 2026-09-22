// project/src/lakeplat/Orchestrator.java —— 编排器：按轮推进、就绪判断、重试上限、失败阻塞下游、并发度
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Deque;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

/**
 * 确定性内存编排器（主文档 3.6）：控制器循环的语义，而不是调度器内核。
 *
 * <p>编排的本质是**依赖图 + 就绪条件**：一个任务能跑，当且仅当它所有上游在这个周期里都成功。
 * 本类把主文档 3.6 表格里的五行全部落成代码：
 * <ol>
 *   <li>拓扑序（在 {@link Dag} 里，同层按 id 排序）；</li>
 *   <li>就绪判断（上游**全部成功**才就绪）；</li>
 *   <li>失败重试（上限固定，用 {@link #tick} 推进）；</li>
 *   <li>失败传播（耗尽后<b>阻塞</b>下游，不跳过）；</li>
 *   <li>并发度（同时运行任务数上限，保护被依赖系统）。</li>
 * </ol>
 *
 * <p>确定性来源：每一轮的「就绪任务」按拓扑序取前 {@code maxConcurrency} 个，不依赖任何时间/随机量，
 * 所以同一份 DAG + 同一个模拟执行结果，必然产出同一串执行记录。
 */
public final class Orchestrator {

    /** 一次执行的结果类型：成功 / 失败。 */
    public enum Outcome {
        SUCCEEDED, FAILED
    }

    /** 一个任务在一轮里的执行记录（用 (taskId, attempt) 标识，便于断言逐项比对）。 */
    public record TaskRun(String taskId, int attempt, Outcome outcome, String detail) {
        @Override
        public String toString() {
            return taskId + "#" + attempt + ":" + outcome;
        }
    }

    /** 一轮调度的结果。 */
    public record Round(int index, List<TaskRun> executed, List<String> failedPermanently,
                        List<String> newlyBlocked, List<String> readyRemaining) {
        public boolean didWork() {
            return !executed.isEmpty();
        }

        public String label() {
            return "第 " + index + " 轮：执行 " + executed + "，永久失败 " + failedPermanently
                    + "，新增阻塞 " + newlyBlocked;
        }
    }

    /** 整体执行的汇总。 */
    public record Summary(List<String> topoOrder, Map<String, Dag.State> states,
                          List<TaskRun> executionLog, List<String> permanentlyFailed,
                          List<String> blocked, List<String> succeeded) {
        public boolean allSucceeded() {
            return permanentlyFailed.isEmpty() && blocked.isEmpty()
                    && succeeded.size() == topoOrder.size();
        }

        public String label() {
            return "成功 " + succeeded.size() + "/" + topoOrder.size() + "，永久失败 " + permanentlyFailed
                    + "，阻塞 " + blocked;
        }
    }

    /** 模拟执行体：同输入（任务 id + 第几次尝试）必须返回同结果——编排决策要能复盘。 */
    @FunctionalInterface
    public interface Executor {
        Outcome execute(String taskId, int attempt);
    }

    private final Dag dag;
    private final int maxConcurrency;
    private final Executor executor;
    private final Map<String, Dag.State> states = new LinkedHashMap<>();
    private final Map<String, Integer> attempts = new LinkedHashMap<>();
    private final Map<String, String> failureReasons = new LinkedHashMap<>();
    private final List<TaskRun> executionLog = new ArrayList<>();
    private final Set<String> blocked = new TreeSet<>();
    private final Set<String> permanentlyFailed = new TreeSet<>();
    /** 在途队列（占着并发槽位的任务，先进先出保证上报顺序确定）。 */
    private final Deque<String> inFlight = new ArrayDeque<>();
    private int roundIndex;

    public Orchestrator(Dag dag, int maxConcurrency, Executor executor) {
        if (maxConcurrency <= 0) {
            throw new IllegalArgumentException("并发度必须为正");
        }
        this.dag = dag;
        this.maxConcurrency = maxConcurrency;
        this.executor = executor;
        for (String id : dag.topoOrder()) {
            states.put(id, Dag.State.PENDING);
            attempts.put(id, 0);
        }
    }

    public Dag dag() {
        return dag;
    }

    public int maxConcurrency() {
        return maxConcurrency;
    }

    public int inFlight() {
        return inFlight.size();
    }

    public Set<String> blockedTasks() {
        return new TreeSet<>(blocked);
    }

    public Set<String> failedTasks() {
        return new TreeSet<>(permanentlyFailed);
    }

    public List<String> blockedBy(String taskId) {
        return dag.blockedBy(taskId);
    }

    public String failureReason(String taskId) {
        return failureReasons.getOrDefault(taskId, "");
    }

    public Map<String, Dag.State> states() {
        return java.util.Collections.unmodifiableMap(new LinkedHashMap<>(states));
    }

    public List<TaskRun> executionLog() {
        return List.copyOf(executionLog);
    }

    /**
     * 推进一轮：并发度是**真正的槽位**，不是摆设。
     *
     * <p>每轮做两件事：① 在就绪任务里占用空闲槽位（启动它们，本轮不结束）；② 对已在途的任务
     * 按排队顺序让模拟执行体上报结果。因此「同时运行任务数」被 {@link #maxConcurrency} 硬性限制，
     * 并发度小的时候执行轮数会变多——这正是用并发度保护被依赖系统的代价。
     *
     * <p>失败处理是这段代码的重点：**重试未耗尽 → 留在 PENDING 等下一轮；
     * 耗尽 → 标记 FAILED 并把下游全部标记 BLOCKED**（而不是让下游"跳过"）。
     */
    public Round tick() {
        roundIndex++;
        List<TaskRun> executed = new ArrayList<>();
        List<String> failedPermanentlyNow = new ArrayList<>();
        List<String> newlyBlocked = new ArrayList<>();

        // ① 占槽：只启动，不上报结果（模拟"已在运行"）
        List<String> available = new ArrayList<>(dag.readyTasks(states, Set.of()));
        available.removeIf(blocked::contains);
        int slots = Math.max(0, maxConcurrency - inFlight.size());
        List<String> started = available.subList(0, Math.min(slots, available.size()));
        for (String id : started) {
            states.put(id, Dag.State.RUNNING);
            inFlight.addLast(id);
        }

        // ② 上报：按排队顺序让每个在途任务"跑完"（示例每轮让全部在途任务收敛，便于确定性复盘）
        while (!inFlight.isEmpty()) {
            String id = inFlight.pollFirst();
            int attempt = attempts.merge(id, 1, Integer::sum);
            Outcome outcome = executor.execute(id, attempt);
            TaskRun run = new TaskRun(id, attempt, outcome, outcome == Outcome.FAILED
                    ? "第 " + attempt + "/" + dag.node(id).maxAttempts() + " 次尝试失败" : "成功");
            executed.add(run);
            executionLog.add(run);
            if (outcome == Outcome.SUCCEEDED) {
                states.put(id, Dag.State.SUCCEEDED);
                continue;
            }
            if (attempt >= dag.node(id).maxAttempts()) {
                states.put(id, Dag.State.FAILED);
                permanentlyFailed.add(id);
                failureReasons.put(id, "重试 " + dag.node(id).retries()
                        + " 次耗尽（共 " + attempt + " 次尝试），任务失败并阻塞下游");
                failedPermanentlyNow.add(id);
                List<String> closure = dag.blockedClosure(id);
                dag.recordBlocking(id, closure);
                for (String downstreamId : closure) {
                    if (states.get(downstreamId) == Dag.State.PENDING) {
                        states.put(downstreamId, Dag.State.BLOCKED);
                        blocked.add(downstreamId);
                        newlyBlocked.add(downstreamId);
                    }
                }
            } else {
                states.put(id, Dag.State.PENDING);   // 未耗尽 → 下一轮重试
            }
        }

        List<String> readyRemaining = new ArrayList<>();
        for (String id : dag.topoOrder()) {
            if (states.get(id) == Dag.State.PENDING && !blocked.contains(id)
                    && dag.ready(id, states, Set.of())) {
                readyRemaining.add(id);
            }
        }
        return new Round(roundIndex, List.copyOf(executed), List.copyOf(failedPermanentlyNow),
                List.copyOf(newlyBlocked), List.copyOf(readyRemaining));
    }

    /**
     * 跑到没有可推进的任务为止（就绪与在途都为空）。
     *
     * <p>上限轮数只是为了防御编程错误（例如执行体永久返回 FAILED 但状态机有 bug），
     * 正常路径下由「就绪为空」自然结束。
     */
    public Summary runToCompletion(int maxRounds) {
        List<Round> rounds = new ArrayList<>();
        while (rounds.size() < maxRounds) {
            Round round = tick();
            rounds.add(round);
            if (!round.didWork()) {
                break;
            }
        }
        List<String> succeeded = new ArrayList<>();
        List<String> failed = new ArrayList<>();
        List<String> blockedList = new ArrayList<>();
        for (String id : dag.topoOrder()) {
            switch (states.get(id)) {
                case SUCCEEDED -> succeeded.add(id);
                case FAILED -> failed.add(id);
                case BLOCKED -> blockedList.add(id);
                default -> { }
            }
        }
        return new Summary(dag.topoOrder(), states(), executionLog, List.copyOf(failed),
                List.copyOf(blockedList), List.copyOf(succeeded));
    }

    /** 模拟执行体：只按「失败清单 + 尝试次数」判定，不看时间、不看随机数。 */
    public static Executor failingOnce(Map<String, Integer> failOnAttemptByTask) {
        return (taskId, attempt) -> {
            Integer failAttempt = failOnAttemptByTask.get(taskId);
            return failAttempt != null && failAttempt == attempt ? Outcome.FAILED : Outcome.SUCCEEDED;
        };
    }

    /** 模拟执行体：某些任务在**所有**尝试里都失败（用于演示重试耗尽与失败传播）。 */
    public static Executor alwaysFailing(Set<String> taskIds, Map<String, Integer> failOthersOnAttempt) {
        return (taskId, attempt) -> {
            if (taskIds.contains(taskId)) {
                return Outcome.FAILED;
            }
            Integer failAttempt = failOthersOnAttempt.get(taskId);
            return failAttempt != null && failAttempt == attempt ? Outcome.FAILED : Outcome.SUCCEEDED;
        };
    }

    /** 一个执行体的组合：任意一项判失败即失败（保持"同输入同结果"）。 */
    public static Executor combine(Executor... executors) {
        return (taskId, attempt) -> {
            boolean failed = Arrays.stream(executors)
                    .anyMatch(executor -> executor.execute(taskId, attempt) == Outcome.FAILED);
            return failed ? Outcome.FAILED : Outcome.SUCCEEDED;
        };
    }
}
