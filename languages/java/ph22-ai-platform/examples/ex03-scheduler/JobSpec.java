// languages/java/ph22-ai-platform/examples/ex03-scheduler/JobSpec.java —— 调度输入：任务定义（调度器只读）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex03 *.java && java -cp /tmp/ph22-ex03 SchedulerDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：9/9 PASS）
//
// 与 ex01 的 JobSpec 相比多了 id 与 estMinutes：
//   id          —— 调度决策的返回物就是它（策略只选 id，不搬对象）；
//   estMinutes  —— 预估运行时长，回填策略用它判断「小任务能否在队头等待窗口内跑完」，
//                  这是回填的全部前提：没有预估就只能 FIFO。
// submitTs 用于 FIFO 排序，priority 用于优先级策略；三者都是提交时定下的不可变意图。
public record JobSpec(String id, String tenant, String name, int gpuCount, int priority,
                      long submitTs, int estMinutes) {

    public JobSpec {
        if (id == null || id.isBlank()) {
            throw new IllegalArgumentException("id 必填");
        }
        if (gpuCount <= 0) {
            throw new IllegalArgumentException("gpuCount 必须为正: " + gpuCount);
        }
        if (estMinutes <= 0) {
            throw new IllegalArgumentException("estMinutes 必须为正: " + estMinutes);
        }
    }

    /** 已排队时长（分钟）。now 由调用方传入，保证同一输入重放出同一决策。 */
    public long waitedMinutes(long now) {
        return Math.max(0L, (now - submitTs) / 60_000L);
    }
}
