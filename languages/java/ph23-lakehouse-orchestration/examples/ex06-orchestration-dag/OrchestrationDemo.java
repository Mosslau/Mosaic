// languages/java/ph23-lakehouse-orchestration/examples/ex06-orchestration-dag/OrchestrationDemo.java —— 编排确定性演练：拓扑序、就绪判断、重试上限、失败阻塞闭包、并发度
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex06 *.java && java -cp /tmp/ph23-ex06 OrchestrationDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：8/8 PASS）
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;

public final class OrchestrationDemo {

    public static void main(String[] args) {
        AtomicInteger pass = new AtomicInteger();
        int total = 8;

        // ---------- 数据（确定性自造）：一条典型湖仓链路 ods → dwd → dws → ads 的编排图 ----------
        Dag dag = new Dag(List.of(
                new TaskNode("ingest", List.of(), 0),
                new TaskNode("clean", List.of("ingest"), 0),
                new TaskNode("dedup", List.of("clean"), 0),
                new TaskNode("dwd_build", List.of("dedup"), 0),
                new TaskNode("dws_dau", List.of("dwd_build"), 2),   // 允许 2 次重试
                new TaskNode("ads_dashboard", List.of("dws_dau"), 0),
                new TaskNode("unrelated_export", List.of(), 0)));   // 与失败分支无关，必须照常跑

        System.out.println("依赖图： " + dag.renderGraph());
        System.out.println("拓扑序： " + dag.renderTopoOrder());

        // A) 拓扑序确定：两次运行完全相同，且同层按 id 升序
        List<String> first = dag.topoOrder();
        List<String> second = dag.topoOrder();
        check(pass, first.equals(second)
                        && first.equals(List.of("ingest", "clean", "dedup", "dwd_build",
                                "dws_dau", "ads_dashboard", "unrelated_export"))
                        && first.indexOf("ingest") < first.indexOf("clean")
                        && first.indexOf("dws_dau") < first.indexOf("ads_dashboard")
                        && !dag.hasCycle(),
                "拓扑序确定性：两次 topoOrder() 完全相同 " + first
                        + "（依赖永远排在下游之前；同层按 id 升序打破平局，所以无依赖的 unrelated_export 在 ingest 之后才被取出）");

        // B) 依赖未完成时不就绪：只有 ingest / unrelated_export 就绪；clean 之后 dedup 才就绪
        List<String> atStart = dag.ready(Set.of(), Set.of());
        List<String> afterClean = dag.ready(Set.of("ingest", "clean"), Set.of());
        List<String> whileRunning = dag.ready(Set.of("ingest", "clean"), Set.of("dedup"));
        check(pass, atStart.equals(List.of("ingest", "unrelated_export"))
                        && afterClean.equals(List.of("dedup", "unrelated_export"))
                        && whileRunning.equals(List.of("unrelated_export")),
                "上游未全部成功就不就绪：初始就绪 " + atStart + "；clean 成功后 " + afterClean
                        + "；dedup 运行中时不重复入队 " + whileRunning);

        // C) 环检测：a→b→c→a 的依赖不可能被满足
        Dag cyclic = new Dag(List.of(
                new TaskNode("a", List.of("c"), 0),
                new TaskNode("b", List.of("a"), 0),
                new TaskNode("c", List.of("b"), 0)));
        check(pass, cyclic.hasCycle() && cyclic.topoOrder().size() < 3 && !dag.hasCycle(),
                "环检测：a→b→c→a 被识别为有环（拓扑序只排出 " + cyclic.topoOrder().size() + "/3 个任务），正常图无环");

        // ---------- 场景 1：暂时性故障 → 重试到成功（不阻塞下游） ----------
        Orchestrator retryRun = new Orchestrator(dag, Set.of(), Map.of("dws_dau", 2));
        int retryRounds = retryRun.runUntilIdle(2);
        System.out.println("场景 1（dws_dau 先失败 2 次）：" + retryRounds + " 轮");
        System.out.println("        " + retryRun.renderFinal());

        // D) 失败重试到上限内成功：共尝试 3 次（2 次失败 + 1 次成功），下游不被阻塞
        check(pass, retryRun.successSet().contains("dws_dau") && retryRun.successSet().contains("ads_dashboard")
                        && dag.failureCount("dws_dau") == 2
                        && retryRun.blockedSet().isEmpty(),
                "失败重试到成功：dws_dau 失败 2 次（上限 2）后第 3 次成功，attempts=" + dag.failureCount("dws_dau")
                        + "，下游 ads_dashboard 未被阻塞");

        // ---------- 场景 2：永久故障 → 重试耗尽标记失败 → 阻塞全部下游且不跳过 ----------
        Dag dag2 = new Dag(List.of(
                new TaskNode("ingest", List.of(), 0),
                new TaskNode("clean", List.of("ingest"), 0),
                new TaskNode("dedup", List.of("clean"), 0),
                new TaskNode("dwd_build", List.of("dedup"), 0),
                new TaskNode("dws_dau", List.of("dwd_build"), 2),
                new TaskNode("ads_dashboard", List.of("dws_dau"), 0),
                new TaskNode("unrelated_export", List.of(), 0)));
        Orchestrator failing = new Orchestrator(dag2, Set.of("dws_dau"), Map.of());
        failing.runUntilIdle(3);
        System.out.println("场景 2（dws_dau 永久失败）：");
        System.out.println("        " + failing.renderFinal());

        // E) 重试上限后标记失败：尝试 retries+1 = 3 次后 FAILED（不会无限重试）
        check(pass, dag2.failureSet().equals(Set.of("dws_dau"))
                        && dag2.failureCount("dws_dau") == 3
                        && failing.states().get("dws_dau") == Orchestrator.TaskState.FAILED,
                "重试上限后标记失败：dws_dau 尝试 " + dag2.failureCount("dws_dau")
                        + " 次（retries=2 → 最多 3 次）后状态 FAILED");

        // F) 失败任务的直接与间接下游都被阻塞（不是跳过、不是成功）
        Set<String> downstreamOfFailed = dag2.blocked(Set.of("dws_dau"));
        boolean downstreamBlocked = downstreamOfFailed.stream()
                .allMatch(id -> failing.states().get(id) == Orchestrator.TaskState.BLOCKED);
        check(pass, downstreamOfFailed.equals(Set.of("ads_dashboard")) && downstreamBlocked
                        && !failing.successSet().contains("ads_dashboard")
                        && failing.successSet().contains("unrelated_export"),
                "失败下游被阻塞而非跳过：blocked=" + downstreamOfFailed + " 全部为 BLOCKED，"
                        + "无关分支 unrelated_export 照常成功");

        // G) 阻塞任务数正确：阻塞集合恰好是失败任务的传递下游闭包，不含失败任务自身
        Dag chain = new Dag(List.of(
                new TaskNode("t1", List.of(), 0),
                new TaskNode("t2", List.of("t1"), 0),
                new TaskNode("t3", List.of("t2"), 1),
                new TaskNode("t4", List.of("t3"), 0),
                new TaskNode("t5", List.of("t4"), 0),
                new TaskNode("side", List.of("t7"), 0),
                new TaskNode("t7", List.of(), 0)));
        Set<String> chainBlocked = chain.blocked(Set.of("t3"));
        check(pass, chainBlocked.equals(Set.of("t4", "t5")) && chainBlocked.size() == 2
                        && !chainBlocked.contains("t3") && chain.blocked(Set.of("side")).isEmpty(),
                "阻塞任务数正确：失败 t3 → 阻塞闭包 " + chainBlocked + "（含间接下游 t5，不含 t3 自身）");

        // H) 并发度限制生效：单轮运行数 ≤ concurrency；正常图全部成功
        Orchestrator limited = new Orchestrator(dag, Set.of(), Map.of());
        int limitedRounds = limited.runUntilIdle(2);
        boolean allRoundsWithin = true;
        for (Orchestrator.Round round : limited.history()) {
            int runningCount = round.running().size();
            if (runningCount > 2) {
                allRoundsWithin = false;
            }
        }
        Orchestrator serial = new Orchestrator(dag, Set.of(), Map.of());
        int serialRounds = serial.runUntilIdle(1);
        check(pass, allRoundsWithin && limited.maxConcurrentObserved() == 2
                        && serial.maxConcurrentObserved() == 1 && serialRounds == 7
                        && limitedRounds == 6 && limitedRounds < serialRounds && limited.allSucceeded(),
                "并发度限制生效：concurrency=2 时单轮最多 " + limited.maxConcurrentObserved() + " 个（"
                        + limitedRounds + " 轮），concurrency=1 时完全串行 " + serialRounds
                        + " 轮（每轮恰好 1 个），全部任务成功");

        System.out.printf("ALL PASS: %d/%d%n", pass.get(), total);
        if (pass.get() != total) {
            System.exit(1);
        }
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
