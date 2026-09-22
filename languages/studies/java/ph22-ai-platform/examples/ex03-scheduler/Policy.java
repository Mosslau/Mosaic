// languages/java/ph22-ai-platform/examples/ex03-scheduler/Policy.java —— 调度策略接口（SPI 同思路：引擎不变，策略可换）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex03 *.java && java -cp /tmp/ph22-ex03 SchedulerDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：9/9 PASS）
//
// 为什么是纯函数：调度决策必须能复盘——「昨天那批任务为什么排了 6 小时」只能靠
// 「同一输入重放出同一决策」回答。因此实现里不许读系统时钟、不许用随机数、
// 不许依赖遍历顺序不确定的集合；输入相同 → 输出必须逐元素相同（测试直接断言这一点）。
// now 由调用方显式传入而非实现自己取，就是为了让时间也成为「输入」的一部分。
import java.util.List;
import java.util.Map;

public interface Policy {
    /** 策略名，用于审计与运维展示（「这一轮是谁做的决策」）。 */
    String name();

    /**
     * 从排队任务中选出本轮要启动的任务（返回任务 id，按启动顺序）。
     *
     * @param queue       排队任务（顺序即提交先后，实现不得就地修改）
     * @param freeGpus    当前空闲卡数
     * @param now         当前时间戳（显式传入，保证决策可重放）
     * @param running     jobId → 已占卡数（回填据此估算队头还要等多久）
     * @param remainingMin jobId → 运行中任务预计剩余分钟数（回填估算队头等待窗口的第二份输入）
     * @return 本轮可启动的任务 id；放不下任何任务时返回空列表（不是抛异常）
     */
    List<String> select(List<JobSpec> queue, int freeGpus, long now, Map<String, Integer> running,
                        Map<String, Integer> remainingMin);

    /** 本轮决策的总卡数：调度器据此推进资源视图，也是回填「不超发」的可断言上界。 */
    default int gpusOf(List<JobSpec> queue, List<String> ids) {
        return ids.stream()
                .mapToInt(id -> queue.stream()
                        .filter(j -> j.id().equals(id))
                        .mapToInt(JobSpec::gpuCount)
                        .findFirst()
                        .orElse(0))
                .sum();
    }

    /** 按 id 取任务；找不到抛异常——调度器绝不返回队列里不存在的任务。 */
    static JobSpec byId(List<JobSpec> queue, String id) {
        return queue.stream()
                .filter(j -> j.id().equals(id))
                .findFirst()
                .orElseThrow(() -> new IllegalStateException("决策引用了队列外的任务: " + id));
    }
}
