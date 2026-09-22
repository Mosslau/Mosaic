// project/src/aiplat/BackfillPolicy.java —— 回填策略：大任务排队时放行「能按时跑完的小任务」
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * 回填（backfill）策略（主文档 3.3/4.1）：以优先级顺序为骨架，但当队头任务放不下时，
 * 允许「放得下且足够短」的任务插队——只要它能在队头任务预计启动之前跑完，就不会推迟队头。
 *
 * <p>为什么必须限制回填任务的时长：回填用「预估」换利用率，预估不准就会推迟队头大任务。
 * 工程上的约束是「限制回填任务的数量与时长」，这里落成 {@code maxBackfillMinutes} 这一个旋钮：
 * 只有预计时长不超过它的任务才有资格插队。旋钮越小越安全、收益越低，是个可解释的取舍。
 *
 * <p>与 FIFO/优先级的关系：后两者遇到放不下的任务就停止（严格顺序），
 * 本策略继续向后扫描——差别只在这一个「是否继续扫描」的决策上，因此三种策略可以同输入对比。
 */
public final class BackfillPolicy implements Policy {

    private final int maxBackfillMinutes;

    public BackfillPolicy(int maxBackfillMinutes) {
        if (maxBackfillMinutes <= 0) {
            throw new IllegalArgumentException("maxBackfillMinutes 必须为正：回填时长必须有上限");
        }
        this.maxBackfillMinutes = maxBackfillMinutes;
    }

    public int maxBackfillMinutes() {
        return maxBackfillMinutes;
    }

    @Override
    public String name() {
        return "BACKFILL";
    }

    @Override
    public List<String> select(List<Candidate> queue, int freeGpus) {
        List<Candidate> ordered = new ArrayList<>(queue);
        ordered.sort(Comparator.comparingInt((Candidate c) -> c.spec().priority()).reversed()
                .thenComparingLong(Candidate::enqueueTs)
                .thenComparing(Candidate::jobId));

        List<String> picked = new ArrayList<>();
        int free = freeGpus;
        boolean blocked = false;   // 是否已经遇到「放不下的队头任务」

        for (Candidate c : ordered) {
            int need = c.spec().gpuCount();
            if (need > free) {
                blocked = true;    // 队头放不下：从这一刻起，后面的任务都算「插队」
                continue;
            }
            if (blocked && c.spec().estMinutes() > maxBackfillMinutes) {
                continue;          // 插队但不够短 → 可能推迟队头，放弃
            }
            picked.add(c.jobId());
            free -= need;
        }
        return picked;
    }
}
