// project/src/aiplat/QuotaGuard.java —— 配额校验：超限拒绝 + 可读原因
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 配额守卫（主文档 3.7）：在任务进入队列之前做校验。
 *
 * <p>为什么是「拒绝」而不是「排队」：排队会让用户以为「等一等就有了」，
 * 而配额不会因为等待而变大——快速失败比长时间等待更友好，这也是平台可用性的一部分。
 *
 * <p>为什么原因必须可读：用户看到的不该是一个 403，而应该是
 * 「配额不足：GPU 12/8（租户 nlp 已占用 8）」——差异化文案能把「催平台」变成「自己调小任务」。
 */
public final class QuotaGuard {

    private final Map<String, Quota> quotas = new LinkedHashMap<>();

    /** 配置租户配额（覆盖旧值）。 */
    public void set(String tenant, Quota quota) {
        quotas.put(tenant, quota);
    }

    public Quota quotaOf(String tenant) {
        return quotas.getOrDefault(tenant, Quota.UNLIMITED);
    }

    /**
     * 校验一次提交。
     *
     * @param tenantGpusInUse       该租户当前已占用的卡数（来自 {@link GpuPool#tenantUsage()}）
     * @param tenantQueuedJobs      该租户当前排队中的任务数
     * @param tenantGpuSecondsToday 该租户今日已消耗的 GPU 秒（来自 {@link MeteringLedger}）
     */
    public Decision check(JobSpec spec, int tenantGpusInUse, int tenantQueuedJobs, long tenantGpuSecondsToday) {
        Quota q = quotaOf(spec.tenant());
        String tenant = spec.tenant();

        // 单任务就把配额撑爆：最直观的一类超限，必须第一个报出来
        if (spec.gpuCount() > q.maxGpus()) {
            return Decision.reject(String.format("配额不足：GPU %d/%d（租户 %s 单任务上限 maxGpus）",
                    spec.gpuCount(), q.maxGpus(), tenant));
        }
        if (tenantGpusInUse + spec.gpuCount() > q.maxGpus()) {
            return Decision.reject(String.format("配额不足：GPU %d/%d（租户 %s 已占用 %d）",
                    tenantGpusInUse + spec.gpuCount(), q.maxGpus(), tenant, tenantGpusInUse));
        }
        if (tenantQueuedJobs + 1 > q.maxQueuedJobs()) {
            return Decision.reject(String.format("配额不足：排队任务 %d/%d（租户 %s）",
                    tenantQueuedJobs + 1, q.maxQueuedJobs(), tenant));
        }
        // 预算维度用「已消耗 + 本任务预计消耗」做前置拦截：跑完才发现超预算就来不及了
        long projected = tenantGpuSecondsToday + (long) spec.gpuCount() * 60L * spec.estMinutes();
        if (projected > q.maxGpuSecondsPerDay()) {
            return Decision.reject(String.format("配额不足：预计今日 GPU 秒 %d/%d（租户 %s 已消耗 %d）",
                    projected, q.maxGpuSecondsPerDay(), tenant, tenantGpuSecondsToday));
        }
        return Decision.allow();
    }

    /** 校验结果：allowed=false 时 reason 一定非空且可读。 */
    public record Decision(boolean allowed, String reason) {
        public static Decision allow() {
            return new Decision(true, "通过");
        }

        public static Decision reject(String reason) {
            return new Decision(false, reason);
        }

        public String describe() {
            return allowed ? "允许" : reason;
        }
    }
}
