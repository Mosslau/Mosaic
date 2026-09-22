// languages/java/ph22-ai-platform/examples/ex03-scheduler/SchedulerDemo.java —— 调度策略主入口：同一输入下三种策略的确定性决策对比
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex03 *.java && java -cp /tmp/ph22-ex03 SchedulerDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：9/9 PASS）
//
// 场景：16 卡的池子，已跑两个任务占 12 卡（剩余时长 10 / 30 分钟），只剩 4 卡；
// 队列头是一个要 8 卡的大任务。FIFO 说「谁都别跑」（4 卡空转），优先级说「高优先级的先跑」，
// 回填说「队头至少还要等 30 分钟，让 30 分钟内能跑完的小任务先占一会」。
// 三种说法都对，区别是可解释的取舍：FIFO 公平但浪费，优先级高效但会饿死低优先级，
// 回填提升利用率但依赖预估准确——本 Demo 用确定性断言把这三笔账算清楚。
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

public final class SchedulerDemo {
    private static final int POOL_TOTAL = 16;
    private static final long NOW = 1_000_000L;

    /** 断言总数：用于末尾 ALL PASS: N/N 与失败退出码。 */
    private static final int TOTAL_CHECKS = 9;

    public static void main(String[] args) {
        // 运行中：8 卡任务剩 10 分钟，4 卡任务剩 30 分钟 → 队头等待窗口 = max(10, 30) = 30 分钟
        Map<String, Integer> running = Map.of("run-a", 8, "run-b", 4);
        Map<String, Integer> remainingMin = Map.of("run-a", 10, "run-b", 30);
        int free = POOL_TOTAL - running.values().stream().mapToInt(Integer::intValue).sum();
        long waitWindow = BackfillPolicy.estimateWaitMinutes(remainingMin);

        // 队列按提交时间构造：j1(8卡,60min) 是队头，后面依次是 2/4/2/2 卡的任务
        List<JobSpec> queue = List.of(
                job("j1", "llm-pretrain", 8, 5, 0L, 60),
                job("j2", "embed-finetune", 2, 9, 10L, 20),
                job("j3", "rerank-train", 4, 3, 20L, 15),
                job("j4", "eval-suite", 2, 7, 30L, 40),
                job("j5", "quick-lora", 2, 1, 40L, 10));

        Policy fifo = new FifoPolicy();
        Policy priority = new PriorityPolicy();
        Policy backfill = new BackfillPolicy();

        List<String> fifoA = fifo.select(queue, free, NOW, running, remainingMin);
        List<String> priorityA = priority.select(queue, free, NOW, running, remainingMin);
        List<String> backfillA = backfill.select(queue, free, NOW, running, remainingMin);

        AtomicInteger pass = new AtomicInteger();

        // 1) 确定性①：同一策略、同一输入连跑两次，决策逐元素相同
        check(pass,
                fifoA.equals(fifo.select(queue, free, NOW, running, remainingMin))
                        && priorityA.equals(priority.select(queue, free, NOW, running, remainingMin))
                        && backfillA.equals(backfill.select(queue, free, NOW, running, remainingMin)),
                "确定性：同一输入跑两遍，三种策略决策序列逐元素相同");

        // 2) 确定性②：新建实例（无内部状态残留）仍给出同一决策 → 策略确实是纯函数
        boolean freshInstancesAgree =
                fifoA.equals(new FifoPolicy().select(queue, free, NOW, running, remainingMin))
                        && priorityA.equals(
                                new PriorityPolicy().select(queue, free, NOW, running, remainingMin))
                        && backfillA.equals(
                                new BackfillPolicy().select(queue, free, NOW, running, remainingMin));
        check(pass, freshInstancesAgree,
                "无状态：全新策略实例给出与旧实例完全相同的决策（纯函数）");

        // 3) FIFO 队头阻塞：8 卡队头放不进 4 卡 → 后面 4 个任务全被卡住，4 卡空转
        check(pass, fifoA.isEmpty(),
                "FIFO 队头阻塞：j1 要 8 卡而只剩 4 卡 → 整队不启动，4 卡空转");

        // 4) 优先级改变顺序：不是 j1 先跑，而是两个高优先级任务先拿卡
        check(pass, priorityA.equals(List.of("j2", "j4")),
                "优先级改变顺序：高优先级 j2(9)/j4(7) 先拿卡（同级回落 FIFO），低优先级 j1/j3 让位");

        // 5) 回填让空转的卡被利用：j1 放不下，j4 预估 40 分钟超出 30 分钟等待窗口，
        //    j2(2卡,20min) 与 j5(2卡,10min) 能在队头等卡期间跑完 → 4 卡被用满
        check(pass, backfillA.equals(List.of("j2", "j5")) && !fifoA.equals(backfillA),
                "回填提升利用率：FIFO 空转 4 卡 → 回填选 j2(2卡,20min) 与 j5(2卡,10min) 用满空闲卡");

        // 6) 回填不挤后队头：本轮选中卡数总和 ≤ 空闲卡数（不超发，队头需要时仍有卡可拿）
        check(pass, backfill.gpusOf(queue, backfillA) <= free,
                "回填不挤后队头：回填选中卡数 " + backfill.gpusOf(queue, backfillA)
                        + " ≤ 空闲卡数 " + free);

        // 7) 回填的两个硬条件：每个插队任务都放得下，且预计时长不超过队头等待窗口
        boolean allFitAndShort = backfillA.stream()
                .map(id -> Policy.byId(queue, id))
                .allMatch(j -> j.gpuCount() <= free && j.estMinutes() <= waitWindow);
        check(pass, allFitAndShort,
                "回填条件：插队任务均放得下且预计时长 ≤ 队头等待窗口(" + waitWindow + "min)");

        // 8) 队头放得下时回填不许插到它前面：队头必须先启动（简化断言）
        List<JobSpec> roomForHead = List.of(
                job("h1", "big-head", 2, 1, 0L, 10),
                job("h2", "later-job", 1, 99, 5L, 5));
        List<String> headFirst = backfill.select(roomForHead, 3, NOW, Map.of(), Map.of());
        check(pass, headFirst.get(0).equals("h1") && backfill.gpusOf(roomForHead, headFirst) <= 3,
                "回填不插队到可启动的队头之前：h1 先启动，回填卡数 ≤ 空闲卡数");

        // 9) 回填不推迟队头：插队任务只吃「队头此刻本来就拿不到」的卡，等队头能启动时
        //    它们已跑完（预估时长 ≤ 等待窗口）；此断言直接验证这条推理的数字前提
        boolean noDelayGuarantee = backfillA.stream()
                .map(id -> Policy.byId(queue, id))
                .allMatch(j -> j.estMinutes() <= waitWindow)
                && fifoA.isEmpty();
        check(pass, noDelayGuarantee,
                "回填不推迟队头：队头等待窗口 " + waitWindow + "min ≥ 所有插队任务预估时长");

        System.out.println("== 同一输入（free=" + free + " 卡，队头等待窗口=" + waitWindow
                + "min）下三种策略的决策序列 ==");
        printDecision(fifo, queue, fifoA);
        printDecision(priority, queue, priorityA);
        printDecision(backfill, queue, backfillA);
        System.out.printf("ALL PASS: %d/%d%n", pass.get(), TOTAL_CHECKS);
        if (pass.get() != TOTAL_CHECKS) {
            System.exit(1);
        }
    }

    private static void printDecision(Policy policy, List<JobSpec> queue, List<String> picked) {
        String detail = picked.isEmpty()
                ? "(空 — 队头放不下，整队等待)"
                : picked.stream()
                        .map(id -> {
                            JobSpec j = Policy.byId(queue, id);
                            return j.id() + "(" + j.gpuCount() + "卡/" + j.estMinutes() + "min)";
                        })
                        .reduce((a, b) -> a + ", " + b)
                        .orElse("");
        System.out.printf("  %-9s -> %s%n", policy.name(), detail);
    }

    private static JobSpec job(String id, String name, int gpus, int priority,
                               long submitTs, int estMinutes) {
        return new JobSpec(id, "acme", name, gpus, priority, NOW - 600_000L + submitTs, estMinutes);
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
