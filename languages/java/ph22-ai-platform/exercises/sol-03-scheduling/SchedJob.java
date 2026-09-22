// exercises/sol-03-scheduling/SchedJob.java —— 调度输入：待排队任务的不可变视图
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol03 *.java && java -cp /tmp/ph22-sol03 Sol03Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）

/**
 * 一个排队任务在调度器眼里的全部信息。
 * submitSeq 是提交序号（越小越早），estimatedSeconds 是预估运行时长——回填策略靠它判断「会不会推迟队头」。
 */
public record SchedJob(String id, String tenant, int priority, int gpus, long submitSeq, long estimatedSeconds) {

    public SchedJob {
        if (id == null || id.isBlank()) {
            throw new IllegalArgumentException("任务 id 不能为空");
        }
        if (priority < 0) {
            throw new IllegalArgumentException("优先级不能为负数：" + priority);
        }
        if (gpus <= 0) {
            throw new IllegalArgumentException("GPU 数量必须为正数：" + gpus);
        }
        if (estimatedSeconds <= 0) {
            throw new IllegalArgumentException("预估时长必须为正数：" + estimatedSeconds);
        }
    }

    @Override
    public String toString() {
        return id + "(prio=" + priority + ",gpus=" + gpus + ",est=" + estimatedSeconds + "s)";
    }
}
