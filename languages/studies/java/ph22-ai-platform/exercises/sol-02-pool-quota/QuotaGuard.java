// exercises/sol-02-pool-quota/QuotaGuard.java —— 租户配额校验：超限拒绝而非排队 + 拒绝原因可读
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol02 *.java && java -cp /tmp/ph22-sol02 Sol02Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：13/13 PASS）

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 配额守卫（对应 22-ai-platform.md 3.7）。
 * 核心纪律：**快速失败比长时间等待更友好**——配额不会因为等待而变大，
 * 所以超限请求既不分配资源、也不进入任何等待队列，只在拒绝日志里留一条可读原因。
 */
public final class QuotaGuard {

    private final Quota quota;
    private final Map<String, Integer> usedGpus = new HashMap<>();
    private final Map<String, Integer> queuedJobs = new HashMap<>();
    private final List<String> rejections = new ArrayList<>();

    public QuotaGuard(Quota quota) {
        this.quota = quota;
    }

    public Quota quota() { return quota; }

    public synchronized int usedGpus(String tenant) {
        return usedGpus.getOrDefault(tenant, 0);
    }

    public synchronized int queuedJobs(String tenant) {
        return queuedJobs.getOrDefault(tenant, 0);
    }

    /** 当前处于「排队」状态的任务总数：配额拒绝不会增加它（拒绝 ≠ 排队）。 */
    public synchronized int pendingTotal() {
        int sum = 0;
        for (int n : queuedJobs.values()) {
            sum += n;
        }
        return sum;
    }

    /** 拒绝日志（可读原因的集合），运维据此回答「为什么这个提交被拒了」。 */
    public synchronized List<String> rejections() {
        return Collections.unmodifiableList(new ArrayList<>(rejections));
    }

    /** GPU 配额校验：超限立刻拒绝并给出可读原因，已用额度不变。 */
    public synchronized AdmissionDecision reserve(String tenant, int gpus) {
        if (tenant == null || tenant.isBlank()) {
            throw new IllegalArgumentException("租户不能为空");
        }
        if (gpus <= 0) {
            String reason = "非法 GPU 数量：" + gpus;
            rejections.add(tenant + " :: " + reason);
            return AdmissionDecision.denied(tenant, gpus, usedGpus(tenant), reason);
        }
        int used = usedGpus(tenant);
        int after = used + gpus;
        if (after > quota.maxGpus()) {
            String reason = String.format("配额不足：GPU %d/%d（已用 %d，申请 %d），请缩减规模或释放后重试",
                    after, quota.maxGpus(), used, gpus);
            rejections.add(tenant + " :: " + reason);
            return AdmissionDecision.denied(tenant, gpus, used, reason);
        }
        usedGpus.put(tenant, after);
        return AdmissionDecision.granted(tenant, gpus, after, quota.maxGpus());
    }

    /** 释放配额。释放超过持有量说明账目已经不一致，必须报错。 */
    public synchronized void release(String tenant, int gpus) {
        if (gpus <= 0) {
            throw new IllegalArgumentException("GPU 数量必须为正数：" + gpus);
        }
        int used = usedGpus(tenant);
        if (gpus > used) {
            throw new IllegalStateException(
                    "释放被拒：租户 " + tenant + " 仅持有 " + used + " 卡，无法释放 " + gpus + " 卡");
        }
        usedGpus.put(tenant, used - gpus);
    }

    /** 排队任务数配额：租户的待排队任务也不能无限增长（否则队列会被单租户打满）。 */
    public synchronized AdmissionDecision enqueue(String tenant) {
        int current = queuedJobs(tenant);
        if (current + 1 > quota.maxQueuedJobs()) {
            String reason = String.format("排队配额不足：%d/%d 个任务（租户 %s），请等待在跑任务结束后再提交",
                    current + 1, quota.maxQueuedJobs(), tenant);
            rejections.add(tenant + " :: " + reason);
            return AdmissionDecision.denied(tenant, 0, usedGpus(tenant), reason);
        }
        queuedJobs.put(tenant, current + 1);
        return AdmissionDecision.granted(tenant, 0, usedGpus(tenant), quota.maxGpus());
    }

    /** 任务离开队列（被调度或被取消）。 */
    public synchronized void dequeue(String tenant) {
        int current = queuedJobs(tenant);
        if (current <= 0) {
            throw new IllegalStateException("出队被拒：租户 " + tenant + " 队列中没有任何任务");
        }
        queuedJobs.put(tenant, current - 1);
    }

    @Override
    public synchronized String toString() {
        return "QuotaGuard[quota=" + quota + " used=" + usedGpus + " queued=" + queuedJobs + "]";
    }
}
