// project/src/aiplat/Quota.java —— 多租户配额（卡数 / 排队数 / 每日 GPU 秒）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

/**
 * 租户配额（主文档 3.7）：一个租户能在共享池子里占多少。
 *
 * <p>三个维度对应三种「被单一租户吃光」的方式：
 * 单任务卡数（一个巨任务）、排队任务数（刷爆队列）、每日 GPU 秒（预算失控）。
 * 只设卡数是不够的——配额必须同时约束「同时占用」和「累计消耗」。
 */
public record Quota(int maxGpus, int maxQueuedJobs, long maxGpuSecondsPerDay) {

    /** 未配置配额的租户：不限制（真实平台会拒绝无配额租户，本阶段演示默认放行）。 */
    public static final Quota UNLIMITED = new Quota(Integer.MAX_VALUE, Integer.MAX_VALUE, Long.MAX_VALUE);

    public Quota {
        if (maxGpus <= 0) throw new IllegalArgumentException("maxGpus 必须为正");
        if (maxQueuedJobs <= 0) throw new IllegalArgumentException("maxQueuedJobs 必须为正");
        if (maxGpuSecondsPerDay <= 0) throw new IllegalArgumentException("maxGpuSecondsPerDay 必须为正");
    }
}
