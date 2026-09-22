// exercises/sol-02-pool-quota/Quota.java —— 租户配额（GPU 上限 + 排队任务数上限）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol02 *.java && java -cp /tmp/ph22-sol02 Sol02Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：13/13 PASS）

/**
 * 配额是「租户在池子里最多能占多少」，与优先级（谁先拿）是两回事：
 * 配额超限**拒绝**，优先级只影响**排队顺序**。
 */
public record Quota(int maxGpus, int maxQueuedJobs) {

    public Quota {
        if (maxGpus <= 0) {
            throw new IllegalArgumentException("GPU 配额必须为正数：" + maxGpus);
        }
        if (maxQueuedJobs < 0) {
            throw new IllegalArgumentException("排队配额不能为负数：" + maxQueuedJobs);
        }
    }

    @Override
    public String toString() {
        return "Quota[maxGpus=" + maxGpus + ", maxQueuedJobs=" + maxQueuedJobs + "]";
    }
}
