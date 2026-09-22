// project/src/aiplat/TrainingJob.java —— 训练任务聚合根：状态机 + 重试上限 + 审计轨迹
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

import java.util.ArrayList;
import java.util.List;

/**
 * 训练任务聚合根（主文档 3.1）：不可变定义（{@link JobSpec}）+ 可变生命周期（{@link JobState}）。
 *
 * <p>三条纪律写在这里而不是散在调用方：
 * <ul>
 *   <li><b>非法迁移挡在聚合内</b>：所有迁移方法先校验当前状态，不合法直接抛 IllegalStateException；</li>
 *   <li><b>重试有上限</b>：只允许 FAILED → QUEUED，attempt 单调递增且不超过 {@value #MAX_ATTEMPTS}；</li>
 *   <li><b>迁移必审计</b>：每次迁移写一条 (ts, from, to, reason, operator)——「谁把任务杀了」是值班第一问。</li>
 * </ul>
 */
public final class TrainingJob {

    /** 重试上限：无上限重试会吃掉整个池子（主文档 3.1）。 */
    public static final int MAX_ATTEMPTS = 3;

    private final String jobId;
    private final JobSpec spec;
    private final String idempotencyKey;
    private final List<AuditEntry> audit = new ArrayList<>();

    private JobState state;
    private int attempt = 1;

    public TrainingJob(String jobId, JobSpec spec, long ts, String operator) {
        this.jobId = jobId;
        this.spec = spec;
        this.idempotencyKey = spec.idempotencyKey();
        this.state = new JobState.Queued(ts);
        this.audit.add(new AuditEntry(ts, "-", "QUEUED", "提交受理（" + spec.ref() + " gpu=" + spec.gpuCount()
                + " prio=" + spec.priority() + "）", operator));
    }

    public String jobId() { return jobId; }
    public JobSpec spec() { return spec; }
    public String idempotencyKey() { return idempotencyKey; }
    public int attempt() { return attempt; }
    public JobState state() { return state; }
    public List<AuditEntry> audit() { return List.copyOf(audit); }

    /** 最近一次入队时间：调度策略按它做同级 FIFO 的稳定排序。 */
    public long queuedAt() {
        return state instanceof JobState.Queued q ? q.sinceTs() : -1L;
    }

    /** 产物 id（仅 SUCCEEDED 有；其余为 null）——模型血缘从它出发。 */
    public String artifactId() {
        return state instanceof JobState.Succeeded s ? s.artifactId() : null;
    }

    /** 终态：SUCCEEDED / CANCELLED，以及 attempt 用尽后的 FAILED。 */
    public boolean isTerminal() {
        return state.isTerminal() || (state instanceof JobState.Failed && attempt >= MAX_ATTEMPTS);
    }

    /** 只有「失败且还没用尽尝试次数」才可重试。 */
    public boolean canRetry() {
        return state instanceof JobState.Failed && attempt < MAX_ATTEMPTS;
    }

    /** QUEUED → RUNNING：由调度器在成功分配 GPU 之后调用。 */
    public void start(long ts, String operator) {
        if (!(state instanceof JobState.Queued q)) {
            throw new IllegalStateException(illegal("RUNNING", state));
        }
        state = new JobState.Running(ts, attempt);
        audit.add(new AuditEntry(ts, q.label(), "RUNNING", "调度器分配 GPU（第 " + attempt + " 次尝试）", operator));
    }

    /** RUNNING → SUCCEEDED：产物 id 必填，因为下游模型登记需要血缘锚点。 */
    public void succeed(long ts, String artifactId) {
        if (!(state instanceof JobState.Running)) {
            throw new IllegalStateException(illegal("SUCCEEDED", state));
        }
        if (artifactId == null || artifactId.isBlank()) {
            throw new IllegalArgumentException("artifactId 必填：成功的训练任务必须能指向产物，否则模型血缘断链");
        }
        state = new JobState.Succeeded(ts, artifactId, attempt);
        audit.add(new AuditEntry(ts, "RUNNING", "SUCCEEDED", "执行体上报成功，产物 " + artifactId, "executor"));
    }

    /** RUNNING → FAILED：失败不释放「是否重试」的决定权，那是人/平台策略的事。 */
    public void fail(long ts, String reason) {
        if (!(state instanceof JobState.Running)) {
            throw new IllegalStateException(illegal("FAILED", state));
        }
        String why = (reason == null || reason.isBlank()) ? "未提供原因" : reason;
        state = new JobState.Failed(ts, why, attempt);
        boolean exhausted = attempt >= MAX_ATTEMPTS;
        audit.add(new AuditEntry(ts, "RUNNING", "FAILED",
                "执行体上报失败：" + why + "（attempt " + attempt + "/" + MAX_ATTEMPTS
                        + (exhausted ? "，尝试次数已用尽" : "，可重试") + "）", "executor"));
    }

    /**
     * FAILED → QUEUED（重试，attempt+1）。
     *
     * <p>超过上限时抛异常而不是静默忽略：静默忽略会让调用方以为「重试成功了」，
     * 而任务其实躺在 FAILED 终态里——这类「静默不一致」正是平台事故的来源。
     */
    public void retry(long ts, String operator) {
        if (!(state instanceof JobState.Failed f)) {
            throw new IllegalStateException(illegal("QUEUED(重试)", state));
        }
        if (attempt >= MAX_ATTEMPTS) {
            throw new IllegalStateException("重试超上限：任务 " + jobId + " 已用尽 "
                    + MAX_ATTEMPTS + " 次尝试（当前 attempt=" + attempt + "），FAILED 为终态");
        }
        attempt++;
        state = new JobState.Queued(ts);
        audit.add(new AuditEntry(ts, f.label(), "QUEUED", "重试第 " + attempt + " 次（上次失败：" + f.reason() + "）", operator));
    }

    /** RUNNING/QUEUED → CANCELLED。FAILED 不直接取消：它要么重试，要么等为终态。 */
    public void cancel(long ts, String operator) {
        if (isTerminal()) {
            throw new IllegalStateException(illegal("CANCELLED", state));
        }
        if (state instanceof JobState.Failed) {
            throw new IllegalStateException("非法迁移：任务 " + jobId + " 处于 FAILED，请走重试或等待尝试次数用尽，不能直接取消");
        }
        String from = state.label();
        state = new JobState.Cancelled(ts, operator);
        audit.add(new AuditEntry(ts, from, "CANCELLED", "人工取消", operator));
    }

    private String illegal(String action, JobState current) {
        return "非法迁移：任务 " + jobId + " 当前 " + current.label() + " 不允许 -> " + action;
    }

    /** 审计条目：一条迁移一个事实，只追加不修改。 */
    public record AuditEntry(long ts, String from, String to, String reason, String operator) {
        public String format() {
            return String.format("[%d] %-9s -> %-9s by %-18s %s", ts, from, to, operator, reason);
        }
    }
}
