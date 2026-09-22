// exercises/sol-03-scheduling/FifoPolicy.java —— FIFO：先到先得，队头放不下就整轮停住
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol03 *.java && java -cp /tmp/ph22-sol03 Sol03Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 最朴素的策略：按提交顺序放行，**遇到第一个放不下的任务就停止本轮**。
 * 这个「停止」正是队头阻塞（head-of-line blocking）的来源：
 * 队头是 8 卡任务、池子只剩 4 卡时，后面所有 1 卡任务全部被卡住。
 */
public final class FifoPolicy implements Policy {

    @Override
    public String name() { return "FIFO"; }

    @Override
    public List<String> select(List<SchedJob> queue, int freeGpus, Map<String, Integer> tenantUsed) {
        int free = freeGpus;
        List<String> selected = new ArrayList<>();
        for (SchedJob job : Policy.submitOrder(queue)) {
            if (job.gpus() > free) {
                break; // 队头阻塞：不跳过、不放过后队小任务
            }
            selected.add(job.id());
            free -= job.gpus();
        }
        return List.copyOf(selected);
    }
}
