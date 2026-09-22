// languages/java/ph23-lakehouse-orchestration/examples/ex06-orchestration-dag/Orchestrator.java —— 确定性编排器：按轮推进、并发度限流、失败重试到上限后阻塞下游（不跳过）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex06 *.java && java -cp /tmp/ph23-ex06 OrchestrationDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：8/8 PASS）
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

/**
 * 内存编排器：把 {@link Dag} 的依赖语义推成一条**可复盘的执行轨迹**。
 *
 * 调度纪律（3.6）：
 *   ① 每轮从「就绪任务」里按 id 升序取任务，最多同时运行 concurrency 个——确定性顺序 + 并发上限；
 *   ② 任务失败走 {@link Dag#onFailure(String)}：未耗尽上限 → 下轮重试；耗尽 → 标记 FAILED；
 *   ③ 失败任务的下游进入 BLOCKED（**显式阻塞，不跳过**），编排器继续推进其它分支；
 *   ④ 每轮决策都打印：`轮次 | 运行=[...] | 成功=[...] | 阻塞=[...]`，值班时能直接 diff。
 *
 * 本类不读系统时间、不并发执行：把「运行中」抽象成一轮的批量状态，于是整条轨迹可复现。
 */
public final class Orchestrator {

    /** 任务状态机：等待 → 运行 → 成功 / 失败 / 被阻塞。 */
    public enum TaskState { PENDING, RUNNING, SUCCEEDED, FAILED, BLOCKED }

    /** 一轮决策的不可变记录。 */
    public record Round(int index, List<String> running, Set<String> success, Set<String> failed,
                        Set<String> blocked) {
        public Round {
            running = List.copyOf(running);
            success = Set.copyOf(success);
            failed = Set.copyOf(failed);
        }
    }

    private final Dag dag;
    private final Set<String> failAlways;
    private final Map<String, Integer> failTimes;
    private final Map<String, TaskState> states = new LinkedHashMap<>();
    private final List<Round> history = new ArrayList<>();
    private int maxConcurrentObserved;

    public Orchestrator(Dag dag) {
        this(dag, Set.of(), Map.of());
    }

    /**
     * @param failAlways 每次尝试都失败的任务（模拟永久故障，用于验证重试上限与下游阻塞）
     * @param failTimes  前 N 次尝试失败、第 N+1 次成功的任务（模拟暂时性故障，用于验证重试后恢复）
     */
    public Orchestrator(Dag dag, Set<String> failAlways, Map<String, Integer> failTimes) {
        this.dag = dag;
        this.failAlways = Set.copyOf(failAlways);
        this.failTimes = Map.copyOf(failTimes);
        for (TaskNode node : dag.tasks()) {
            states.put(node.id(), TaskState.PENDING);
        }
    }

    /**
     * 推进到没有任何可动作为止。返回真正执行的「轮次」数（每个轮次 = 一批并发运行的任务）。
     * 每个任务在同一轮里只运行一次；失败重试发生在后续轮次，因此重试不会挤占同一轮的并发额度。
     */
    public int runUntilIdle(int concurrency) {
        if (concurrency < 1) {
            throw new IllegalArgumentException("并发度必须 ≥ 1：" + concurrency);
        }
        int roundIndex = 0;
        while (true) {
            List<String> justRan = new ArrayList<>();
            for (String id : readyToRun()) {
                if (justRan.size() >= concurrency) {
                    break;   // 并发上限：本轮不再接新任务
                }
                states.put(id, TaskState.RUNNING);
                justRan.add(id);
            }
            if (justRan.isEmpty()) {
                break;   // 没有就绪任务：要么全部收敛，要么剩下的是被阻塞的（都显式留在状态里）
            }
            for (String id : justRan) {
                states.put(id, decide(id));
            }
            maxConcurrentObserved = Math.max(maxConcurrentObserved, justRan.size());

            Set<String> failed = dag.failureSet();
            Set<String> blocked = dag.blocked(failed);
            for (String id : blocked) {
                if (states.get(id) != TaskState.SUCCEEDED) {
                    states.put(id, TaskState.BLOCKED);
                }
            }
            roundIndex++;
            Round round = new Round(roundIndex, justRan, successSet(), failed, blocked);
            history.add(round);
            System.out.println(renderRound(round));
        }
        return roundIndex;
    }

    /**
     * 单个任务这次尝试的结果：永久失败 → FAILED；暂时性失败 → 重试或 FAILED；否则 SUCCEEDED。
     * 注意「重试耗尽」必须在此刻落成 FAILED，不能让它留在 PENDING——否则它每轮都就绪，
     * 失败计数无限增长而下游永远等不到结论（这正是真实调度里最危险的活锁形态）。
     */
    private TaskState decide(String id) {
        int attempt = dag.failureCount(id) + 1;
        boolean fails = failAlways.contains(id) || attempt <= failTimes.getOrDefault(id, 0);
        if (!fails) {
            return TaskState.SUCCEEDED;
        }
        Dag.FailureAction action = dag.onFailure(id);
        return action == Dag.FailureAction.FAIL ? TaskState.FAILED : TaskState.PENDING;
    }

    /**
     * 本轮真正可以运行的任务：{@link Dag#ready} 给出「依赖满足」的候选，再按本地状态过滤掉
     * 已失败/已阻塞/已完成/运行中的任务——Dag 只看依赖，不知道某个任务已经耗尽重试。
     * 少这一层过滤就是活锁：失败任务每轮都「就绪」，计数无限增长而下游永远等不到结论。
     */
    private List<String> readyToRun() {
        List<String> ready = new ArrayList<>();
        for (String id : dag.ready(successSet(), running())) {
            if (states.get(id) == TaskState.PENDING) {
                ready.add(id);
            }
        }
        return ready;
    }

    private Set<String> running() {
        Set<String> running = new TreeSet<>();
        states.forEach((id, state) -> {
            if (state == TaskState.RUNNING) {
                running.add(id);
            }
        });
        return running;
    }

    /** 成功集合：Dag.ready 的就绪条件只认「上游全部成功」。 */
    public Set<String> successSet() {
        Set<String> success = new TreeSet<>();
        states.forEach((id, state) -> {
            if (state == TaskState.SUCCEEDED) {
                success.add(id);
            }
        });
        return success;
    }

    public Set<String> failedSet() {
        return dag.failureSet();
    }

    public Set<String> blockedSet() {
        return dag.blocked(dag.failureSet());
    }

    public Map<String, TaskState> states() {
        return Map.copyOf(states);
    }

    public List<Round> history() {
        return List.copyOf(history);
    }

    public int maxConcurrentObserved() {
        return maxConcurrentObserved;
    }

    public boolean allSucceeded() {
        return states.values().stream().allMatch(state -> state == TaskState.SUCCEEDED);
    }

    public String renderRound(Round round) {
        return "轮次 " + round.index()
                + " | 运行=" + round.running()
                + " | 成功=" + new TreeSet<>(round.success())
                + " | 失败=" + new TreeSet<>(round.failed())
                + " | 阻塞=" + new TreeSet<>(round.blocked());
    }

    /** 一屏终态：`id=STATE` 按 id 升序，外加失败/阻塞两个显式集合。 */
    public String renderFinal() {
        StringBuilder sb = new StringBuilder();
        sb.append("终态：");
        for (Map.Entry<String, TaskState> entry : states.entrySet()) {
            if (sb.charAt(sb.length() - 1) != '：') {
                sb.append(' ');
            }
            sb.append(entry.getKey()).append('=').append(entry.getValue());
        }
        sb.append(" | 失败=").append(failedSet()).append(" | 阻塞=").append(blockedSet());
        return sb.toString();
    }
}
