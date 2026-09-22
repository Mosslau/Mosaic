// languages/java/ph22-ai-platform/examples/ex07-quota-metering/Quota.java —— 租户配额：GPU 卡数上限、排队任务上限、每日 GPU 秒上限
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex07 *.java && java -cp /tmp/ph22-ex07 QuotaMeteringDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：9/9 PASS）

/**
 * 配额是「租户在池子里最多能占多少」，与优先级（谁先拿卡）是两件事：
 * 优先级只决定排队顺序，配额决定能不能进队——所以超配额的请求在提交口就被拒绝，不进入调度。
 * 日 GPU 秒上限是成本闸门：卡数不超但一天跑 100 个短任务，同样能把预算烧穿，因此必须单独计量。
 */
public record Quota(int maxGpus, int maxQueuedJobs, long maxGpuSecondsPerDay) {

    public Quota {
        if (maxGpus < 0 || maxQueuedJobs < 0 || maxGpuSecondsPerDay < 0) {
            throw new IllegalArgumentException("配额不能为负：" + maxGpus + "/" + maxQueuedJobs + "/" + maxGpuSecondsPerDay);
        }
    }
}
