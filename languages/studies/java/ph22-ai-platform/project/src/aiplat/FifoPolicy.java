// project/src/aiplat/FifoPolicy.java —— FIFO：按提交时间先到先得（含队头阻塞）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * FIFO 策略（主文档 3.3）：按入队时间先到先得。
 *
 * <p>关键实现细节：一旦队头任务放不下就<b>立刻停止</b>（队头阻塞）。
 * 这不是保守，而是 FIFO 的定义——如果跳过队头去选后面的任务，那已经是回填策略了。
 * 队头阻塞正是「8 卡任务阻塞一堆 1 卡任务」这一容量陷阱的来源（主文档 4.1）。
 */
public final class FifoPolicy implements Policy {

    @Override
    public String name() {
        return "FIFO";
    }

    @Override
    public List<String> select(List<Candidate> queue, int freeGpus) {
        List<Candidate> ordered = new ArrayList<>(queue);
        // 入队时间相同则按 jobId 兜底排序，保证同输入决策唯一（避免依赖集合迭代顺序）
        ordered.sort(Comparator.comparingLong(Candidate::enqueueTs).thenComparing(Candidate::jobId));

        List<String> picked = new ArrayList<>();
        int free = freeGpus;
        for (Candidate c : ordered) {
            if (c.spec().gpuCount() > free) {
                break;   // 队头阻塞：后面的任务一律不放行
            }
            picked.add(c.jobId());
            free -= c.spec().gpuCount();
        }
        return picked;
    }
}
