// languages/java/ph22-ai-platform/examples/ex03-scheduler/FifoPolicy.java —— FIFO：先到先得，队头放不下就整队等
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex03 *.java && java -cp /tmp/ph22-ex03 SchedulerDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：9/9 PASS）
//
// FIFO 的语义是「不许后到者插队」：只要队头放不下，它后面所有任务都不能启动——
// 这就是队头阻塞（head-of-line blocking）。它最公平也最容易被容量陷阱坑到：
// 一个 8 卡任务排在第 1 位，池子里只剩 4 卡时，后面 10 个 1 卡任务全部空等，
// 4 张卡白白空转——回填策略存在的全部理由就是消灭这种空转。
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

public final class FifoPolicy implements Policy {

    @Override
    public String name() {
        return "FIFO";
    }

    @Override
    public List<String> select(List<JobSpec> queue, int freeGpus, long now,
                               Map<String, Integer> running,
                               Map<String, Integer> remainingMin) {
        // 先按提交时间排序（同刻提交用 id 兜底，保证顺序确定，不依赖输入列表的偶然次序）
        List<JobSpec> ordered = new ArrayList<>(queue);
        ordered.sort(Comparator.comparingLong(JobSpec::submitTs).thenComparing(JobSpec::id));

        List<String> picked = new ArrayList<>();
        int remaining = freeGpus;
        for (JobSpec job : ordered) {
            if (job.gpuCount() > remaining) {
                break;                    // 队头放不下 → 后面的一律不等（不插队）
            }
            picked.add(job.id());
            remaining -= job.gpuCount();
        }
        return picked;
    }
}
