// languages/java/ph22-ai-platform/examples/ex03-scheduler/PriorityPolicy.java —— 优先级：高优先先拿卡，同级 FIFO
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex03 *.java && java -cp /tmp/ph22-ex03 SchedulerDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：9/9 PASS）
//
// 为什么同级必须回落到 FIFO：若同级之间顺序不确定，「同一输入 → 同一决策」就不成立，
// 复盘时无法解释「为什么这次先跑的是 A 而不是同优先级的 B」。
// 纯优先级的已知代价是低优先级可能饿死（工业做法叠加等待老化 + 每租户配额，见主文档 4.1）。
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

public final class PriorityPolicy implements Policy {

    @Override
    public String name() {
        return "PRIORITY";
    }

    @Override
    public List<String> select(List<JobSpec> queue, int freeGpus, long now,
                               Map<String, Integer> running,
                               Map<String, Integer> remainingMin) {
        List<JobSpec> ordered = new ArrayList<>(queue);
        // 主键：优先级降序；次键：提交时间升序；末键：id，保证全序且确定
        ordered.sort(Comparator.comparingInt(JobSpec::priority).reversed()
                .thenComparingLong(JobSpec::submitTs)
                .thenComparing(JobSpec::id));

        List<String> picked = new ArrayList<>();
        int remaining = freeGpus;
        for (JobSpec job : ordered) {
            if (job.gpuCount() <= remaining) {
                picked.add(job.id());
                remaining -= job.gpuCount();
            }
            // 放不下的继续往后看：优先级高的放不下，不该挡住优先级稍低但放得下的任务
        }
        return picked;
    }
}
