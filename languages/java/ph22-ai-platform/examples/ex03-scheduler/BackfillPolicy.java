// languages/java/ph22-ai-platform/examples/ex03-scheduler/BackfillPolicy.java —— 回填：大任务放不下时，让「跑得快的小任务」先占空闲卡
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex03 *.java && java -cp /tmp/ph22-ex03 SchedulerDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：9/9 PASS）
//
// 回填的全部价值：队头大任务在等卡时，那些「卡数放得下、且预计时长不超过队头预计等待」
// 的小任务先跑，把本来会空转的卡用掉。
// 回填的全部风险：预估不准就会反过来推迟队头任务，所以必须同时满足两个条件才允许插队：
//   ① 卡数条件：gpuCount ≤ 当前空闲卡数（不可能挤占队头一旦获得的资源）；
//   ② 时长条件：estMinutes ≤ 队头预计等待（等队头要等多久，就只放跑得了这么久的任务）。
// 本示例的「队头预计等待」用运行中任务的剩余时长估算：**取所有运行中任务剩余分钟数的
// 最大值**——池子此刻是满的，队头要等的是「最后一个占着卡的持有者」释放，
// 因此这是「最早可能腾出资源」的保守上界。真实平台会按卡数与释放顺序做更细的
// 可用性预测（甚至按分位数给置信区间），但那需要真实运行时数据，与「纯函数、可重放」
// 的要求冲突，故此处显式简化，并在 Demo 里把这个口径写成可断言的约束。
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

public final class BackfillPolicy implements Policy {

    @Override
    public String name() {
        return "BACKFILL";
    }

    @Override
    public List<String> select(List<JobSpec> queue, int freeGpus, long now,
                               Map<String, Integer> running,
                               Map<String, Integer> remainingMin) {
        List<JobSpec> ordered = new ArrayList<>(queue);
        ordered.sort(Comparator.comparingLong(JobSpec::submitTs).thenComparing(JobSpec::id));

        List<String> picked = new ArrayList<>();
        if (ordered.isEmpty()) {
            return picked;
        }

        JobSpec head = ordered.get(0);
        long estimateWaitMinutes = estimateWaitMinutes(remainingMin);

        // 1) 队头一定最先考虑：放得下就先安排它，这是「回填不推迟队头」的第一层保证
        if (head.gpuCount() <= freeGpus) {
            picked.add(head.id());
        }

        // 2) 剩余空闲卡上，按「小任务优先」装填：卡数升序，同卡数回落 FIFO。
        //    为什么升序而不是 FIFO：回填的考点是「把空闲卡用掉」，先装小任务能把卡用得更碎更满，
        //    而「不许推迟队头」由时长条件与队头优先保证，与装填顺序无关。
        //    同卡数回落 FIFO 是为了让决策可复盘（否则「为什么先跑的是 B」无法解释）。
        List<JobSpec> candidates = new ArrayList<>(ordered);
        candidates.sort(Comparator.comparingInt(JobSpec::gpuCount)
                .thenComparingLong(JobSpec::submitTs)
                .thenComparing(JobSpec::id));

        int remaining = freeGpus - gpusOf(ordered, picked);
        for (JobSpec job : candidates) {
            if (job.id().equals(head.id())) {
                continue;                 // 队头已单独处理，避免重复
            }
            if (job.gpuCount() > remaining) {
                continue;                 // 卡数条件不满足：跳过，继续找更小的
            }
            if (job.estMinutes() > estimateWaitMinutes) {
                continue;                 // 时长条件不满足：跑不完就不许插队
            }
            picked.add(job.id());
            remaining -= job.gpuCount();
        }
        return picked;
    }

    /** 队头等待窗口（分钟）：运行中任务剩余时长的最大值；没有运行中任务则为 0（不许插队）。 */
    public static long estimateWaitMinutes(Map<String, Integer> remainingMin) {
        return remainingMin.values().stream().mapToLong(Integer::intValue).max().orElse(0L);
    }
}
