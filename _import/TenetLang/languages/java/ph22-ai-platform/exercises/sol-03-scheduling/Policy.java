// exercises/sol-03-scheduling/Policy.java —— 可插拔调度策略接口（SPI 同思路：引擎不变，策略可换）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol03 *.java && java -cp /tmp/ph22-sol03 Sol03Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

/**
 * 调度策略：从排队任务中选出本轮可运行的任务 id。
 * 契约：**纯函数**——不修改入参、不依赖随机与时钟，同一输入必须给出同一决策
 * （否则「为什么昨天那批任务排了 6 小时」无法复盘）。
 */
public interface Policy {

    String name();

    /**
     * @param queue      排队任务，按提交顺序给出（只读，实现不得修改）
     * @param freeGpus   当前空闲卡数
     * @param tenantUsed 各租户已占用卡数（公平性兜底用的钩子，本练习的两个策略暂不使用）
     * @return 本轮放行的任务 id（按放行顺序）
     */
    List<String> select(List<SchedJob> queue, int freeGpus, Map<String, Integer> tenantUsed);

    /** 公共排序：优先级降序，同级按提交序号（同级 FIFO）。 */
    static List<SchedJob> priorityOrder(List<SchedJob> queue) {
        List<SchedJob> sorted = new ArrayList<>(queue);
        sorted.sort(Comparator.comparingInt(SchedJob::priority).reversed()
                .thenComparingLong(SchedJob::submitSeq));
        return sorted;
    }

    /** 提交顺序（FIFO 基准序）。 */
    static List<SchedJob> submitOrder(List<SchedJob> queue) {
        List<SchedJob> sorted = new ArrayList<>(queue);
        sorted.sort(Comparator.comparingLong(SchedJob::submitSeq));
        return sorted;
    }
}
