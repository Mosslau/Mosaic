// project/src/aiplat/PriorityPolicy.java —— 优先级策略：高优先级先拿卡，同级 FIFO
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * 优先级策略（主文档 3.3）：优先级降序，同级按入队时间升序。
 *
 * <p>和 FIFO 一样在第一个放不下的任务处停止（不做回填）：优先级只决定「谁排在前面」，
 * 「跳过前面的大任务去塞后面的小任务」是另一种策略（{@link BackfillPolicy}），
 * 把两者混在一起会让调度决策无法解释——这就是「策略即数据、可对比」的价值。
 *
 * <p>已知代价：纯优先级会让低优先级饿死。工业做法是优先级 + 等待时间老化 + 每租户配额三者叠加，
 * 本阶段由 {@link QuotaGuard} 提供配额兜底，老化留给扩展方向。
 */
public final class PriorityPolicy implements Policy {

    @Override
    public String name() {
        return "PRIORITY";
    }

    @Override
    public List<String> select(List<Candidate> queue, int freeGpus) {
        List<Candidate> ordered = new ArrayList<>(queue);
        ordered.sort(Comparator.comparingInt((Candidate c) -> c.spec().priority()).reversed()
                .thenComparingLong(Candidate::enqueueTs)
                .thenComparing(Candidate::jobId));

        List<String> picked = new ArrayList<>();
        int free = freeGpus;
        for (Candidate c : ordered) {
            if (c.spec().gpuCount() > free) {
                break;   // 高优先级大任务放不下 → 不再降低优先级去挑，保持决策可解释
            }
            picked.add(c.jobId());
            free -= c.spec().gpuCount();
        }
        return picked;
    }
}
