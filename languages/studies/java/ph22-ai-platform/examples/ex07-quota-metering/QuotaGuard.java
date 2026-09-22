// languages/java/ph22-ai-platform/examples/ex07-quota-metering/QuotaGuard.java —— 提交前配额校验：超限返回可读原因（拒绝），而不是静默排队
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex07 *.java && java -cp /tmp/ph22-ex07 QuotaMeteringDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：9/9 PASS）
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

/**
 * 为什么返回 Optional&lt;String&gt; 而不是 boolean：拒绝必须**可解释**。
 * 用户看到「配额不足：GPU 12/8」才知道该缩任务还是该申请提额；只回一个 false，
 * 工单里就会出现「平台说不行但没说为什么」。返回值有三态含义：
 *   Optional.empty()  = 允许提交；Optional.of(原因) = 拒绝并给出原因。
 * 校验是**纯函数**（不改任何状态、不写台账）：超限拒绝而不是排队——配额不会因为等待而变大，
 * 让用户等一个永远不会到来的资源，比立刻失败更差（3.7）。
 */
public final class QuotaGuard {

    private final Map<String, Quota> quotas = new LinkedHashMap<>();

    public QuotaGuard put(String tenant, Quota quota) {
        quotas.put(tenant, quota);
        return this;
    }

    public Optional<Quota> quotaOf(String tenant) {
        return Optional.ofNullable(quotas.get(tenant));
    }

    /**
     * 校验一次提交：requestGpus 是本次申请的卡数，queuedJobs 是该租户当前排队数，
     * usedGpuSecondsToday 是今日已消耗的 GPU·秒（来自 MeteringLedger 的累计值）。
     */
    public Optional<String> check(String tenant, int requestGpus, int queuedJobs, long usedGpuSecondsToday) {
        Quota quota = quotas.get(tenant);
        if (quota == null) {
            return Optional.of("未登记租户：" + tenant);
        }
        if (requestGpus <= 0) {
            return Optional.of("非法请求：GPU " + requestGpus);
        }
        if (requestGpus > quota.maxGpus()) {
            return Optional.of("配额不足：GPU " + requestGpus + "/" + quota.maxGpus());
        }
        int queuedAfter = queuedJobs + 1;   // 本次提交本身也要占一个排队位
        if (queuedAfter > quota.maxQueuedJobs()) {
            return Optional.of("排队超限：排队任务 " + queuedAfter + "/" + quota.maxQueuedJobs());
        }
        if (usedGpuSecondsToday >= quota.maxGpuSecondsPerDay()) {
            return Optional.of("配额不足：今日 GPU 秒 " + usedGpuSecondsToday + "/" + quota.maxGpuSecondsPerDay());
        }
        return Optional.empty();
    }
}
