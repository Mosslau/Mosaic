// exercises/sol-01-job-lifecycle/TrainingJob.java —— 任务聚合根：状态机 + 重试上限 + 审计轨迹
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol01 *.java && java -cp /tmp/ph22-sol01 Sol01Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：11/11 PASS）

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 训练任务聚合根。三条纪律：① 非法迁移抛异常且不写审计；② 终态不可变；③ 重试有上限。
 */
public final class TrainingJob {

    private final String jobId;
    private final JobSpec spec;
    private final int maxAttempts;
    private final List<AuditEntry> audit = new ArrayList<>();

    private JobState state = new Queued();
    private int attempt = 1;

    public TrainingJob(String jobId, JobSpec spec, int maxAttempts) {
        if (maxAttempts < 1) {
            throw new IllegalArgumentException("重试上限必须 >= 1：" + maxAttempts);
        }
        this.jobId = jobId;
        this.spec = spec;
        this.maxAttempts = maxAttempts;
    }

    public String jobId() { return jobId; }

    public JobSpec spec() { return spec; }

    public synchronized JobState state() { return state; }

    public int attempt() { return attempt; }

    public int maxAttempts() { return maxAttempts; }

    public synchronized int auditSize() { return audit.size(); }

    /** 审计轨迹的只读快照（调用方改不动内部列表）。 */
    public synchronized List<AuditEntry> audit() { return Collections.unmodifiableList(new ArrayList<>(audit)); }

    /**
     * 唯一的状态推进入口。非法迁移在做任何修改之前就被拒绝，因此不会留下审计。
     */
    public synchronized void transition(JobState to, String reason, String operator) {
        if (to == null) {
            throw new IllegalArgumentException("目标状态不能为空");
        }
        if (!legal(state, to)) {
            throw new IllegalStateException(
                    "非法状态迁移: " + state.name() + " → " + to.name() + "（任务 " + jobId + "）");
        }
        String from = state.name();
        state = to;
        audit.add(new AuditEntry(audit.size() + 1L, Instant.now(), from, to.name(), reason, operator));
    }

    /** 失败重试：只有 FAILED 可重试，attempt 单调递增且不超过上限。 */
    public synchronized void retry(String operator) {
        if (!(state instanceof Failed)) {
            throw new IllegalStateException("仅 FAILED 任务可重试，当前状态: " + state.name());
        }
        if (attempt >= maxAttempts) {
            throw new IllegalStateException(
                    "重试次数已达上限 " + maxAttempts + "（attempt=" + attempt + "），任务 " + jobId + " 需人工介入");
        }
        attempt++;
        transition(new Queued(), "retry attempt " + attempt, operator);
    }

    /** 迁移合法性表——状态机的全部规则集中在这一处。 */
    public static boolean legal(JobState from, JobState to) {
        if (from instanceof Queued) {
            return to instanceof Running || to instanceof Cancelled;
        }
        if (from instanceof Running) {
            return to instanceof Succeeded || to instanceof Failed || to instanceof Cancelled;
        }
        if (from instanceof Failed) {
            return to instanceof Queued;
        }
        return false; // Succeeded / Cancelled 终态不可变
    }

    @Override
    public String toString() {
        return jobId + "[" + spec.tenant() + "/" + spec.name() + " " + spec.gpus() + "GPU "
                + state.name() + " attempt=" + attempt + "/" + maxAttempts + "]";
    }
}
