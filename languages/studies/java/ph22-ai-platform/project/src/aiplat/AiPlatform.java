// project/src/aiplat/AiPlatform.java —— 控制面门面：把提交/调度/生命周期/台账/发布编成一条闭环
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * AI 平台最小控制面（主文档第 7 章「阶段项目」）：把各领域件编成一条闭环流水线。
 *
 * <pre>
 * 提交（配额 + 幂等）→ 排队 → 调度决策（GPU 池）→ 生命周期推进（含失败重试）
 *   → 产物登记为模型版本（血缘 + 晋级）→ 推理服务灰度发布（收敛 + 回滚）→ 运维一屏 + 指标
 * </pre>
 *
 * <p>门面的职责是<b>编排</b>而不是<b>实现</b>：状态机在 {@link TrainingJob}，账本在 {@link GpuPool}
 * 与 {@link MeteringLedger}，策略在 {@link Policy}，纪律在 {@link ModelRegistry}。
 * 门面负责让它们按正确顺序发生，并把跨域动作（例如「任务进入终态就释放 GPU 并写计量事件」）收拢到一处——
 * 这样「漏释放」「漏记账」这类跨域 bug 只有一个地方可能出错。
 *
 * <p>时钟是<b>固定逻辑时钟</b>（每次变更 +60 秒）：全部数据确定性自造，不读系统时间、不读外部文件，
 * 因此同一份代码在任何机器上跑出的审计与计量数值都一致。
 */
public final class AiPlatform {

    /** 逻辑时钟起点：2023-11-14T22:13:20Z，固定值保证可复现。 */
    private static final long BASE_TS = 1_700_000_000_000L;
    /** 每次状态变更推进 60 秒：让审计时间戳与 GPU 秒计量都有确定值。 */
    private static final long TICK_MS = 60_000L;

    private final GpuPool pool;
    private final Policy policy;
    private final QuotaGuard quotaGuard = new QuotaGuard();
    private final MeteringLedger meter = new MeteringLedger();
    private final ModelRegistry registry = new ModelRegistry();
    private final DatasetVersion.Ledger datasets = new DatasetVersion.Ledger();

    private final Map<String, TrainingJob> jobs = new LinkedHashMap<>();
    private final Map<String, String> idempotencyIndex = new HashMap<>();
    private final Map<String, InferenceService> services = new LinkedHashMap<>();
    private final List<String> audit = new ArrayList<>();

    private int seq;
    private long clock = BASE_TS;

    public AiPlatform(int totalGpus, Policy policy) {
        this.pool = new GpuPool(totalGpus);
        this.policy = policy;
    }

    // ------------------------------------------------------------------ 只读访问

    public GpuPool pool() { return pool; }
    public Policy policy() { return policy; }
    public QuotaGuard quotaGuard() { return quotaGuard; }
    public MeteringLedger meter() { return meter; }
    public ModelRegistry registry() { return registry; }
    public DatasetVersion.Ledger datasets() { return datasets; }
    public List<String> audit() { return List.copyOf(audit); }
    public long now() { return clock; }
    public int jobCount() { return jobs.size(); }

    public Optional<TrainingJob> job(String jobId) {
        return Optional.ofNullable(jobs.get(jobId));
    }

    public long countByState(String label) {
        return jobs.values().stream().filter(j -> j.state().label().equals(label)).count();
    }

    public int queuedCount() {
        return (int) countByState("QUEUED");
    }

    public int runningCount() {
        return (int) countByState("RUNNING");
    }

    /** 排队任务的只读视图（入队顺序），调度策略的输入。 */
    public List<Policy.Candidate> queueSnapshot() {
        List<Policy.Candidate> queue = new ArrayList<>();
        for (TrainingJob j : jobs.values()) {
            if (j.state() instanceof JobState.Queued) {
                queue.add(new Policy.Candidate(j.jobId(), j.spec(), j.queuedAt()));
            }
        }
        return queue;
    }

    // ------------------------------------------------------------------ 提交（3.1 / 3.7）

    /**
     * 提交任务：先查幂等，再校验配额，最后才创建聚合根。
     *
     * <p>顺序很重要：幂等必须排在配额前面——否则「用户重发同一个任务」会被当成新增，
     * 在配额边缘偶发地被拒，用户看到的是「同一件事一次成功一次失败」。
     */
    public SubmitResult submit(JobSpec spec) {
        String key = spec.idempotencyKey();
        String existing = idempotencyIndex.get(key);
        if (existing != null) {
            audit.add("幂等命中：key=" + key + " → 返回原任务 " + existing);
            return new SubmitResult(existing, true, "幂等命中：返回原任务 " + existing);
        }

        int tenantGpusInUse = pool.tenantUsage().getOrDefault(spec.tenant(), 0);
        int tenantQueued = 0;
        for (TrainingJob j : jobs.values()) {
            if (j.spec().tenant().equals(spec.tenant()) && j.state() instanceof JobState.Queued) {
                tenantQueued++;
            }
        }
        long tenantSecondsToday = meter.gpuSecondsOnDay(spec.tenant(), now() / 86_400_000L);

        QuotaGuard.Decision decision = quotaGuard.check(spec, tenantGpusInUse, tenantQueued, tenantSecondsToday);
        if (!decision.allowed()) {
            // 拒绝的提交不进队列、不占幂等键：用户的修正是「改小任务后重新提交」，不应被幂等挡住
            audit.add("提交被拒：" + spec.ref() + " —— " + decision.reason());
            return new SubmitResult(null, false, decision.reason());
        }

        String jobId = String.format("job-%04d", ++seq);
        TrainingJob job = new TrainingJob(jobId, spec, tick(), "submit");
        jobs.put(jobId, job);
        idempotencyIndex.put(key, jobId);
        audit.add("提交受理：" + jobId + " " + spec.ref() + " gpu=" + spec.gpuCount() + " prio=" + spec.priority());
        return new SubmitResult(jobId, false, "受理：" + jobId);
    }

    // ------------------------------------------------------------------ 调度（3.2 / 3.3）

    /**
     * 跑一轮调度：策略给决策，门面负责「分配 GPU + 推进状态机」这两件有副作用的事。
     *
     * <p>决策（纯函数）与执行（改账本 + 改状态）分开，是为了让「为什么这么排」可复盘：
     * 同样的队列 + 同样的空闲卡数，一定能重放出同样的决策。
     */
    public List<String> schedule() {
        List<Policy.Candidate> queue = queueSnapshot();
        List<String> picked = policy.select(queue, pool.free());
        for (String jobId : picked) {
            TrainingJob job = require(jobId);
            if (!pool.tryAllocate(jobId, job.spec().tenant(), job.spec().gpuCount(), tick())) {
                throw new IllegalStateException("调度决策与实际空闲不一致：策略选中 " + jobId
                        + " 但池子放不下（free=" + pool.free() + "）——策略必须是纯函数，这种不一致是 bug");
            }
            job.start(tick(), "scheduler/" + policy.name());
        }
        if (!picked.isEmpty()) {
            audit.add("调度轮次(" + policy.name() + ")：free=" + (pool.free() + allocatedBy(picked)) + " → 分配 " + picked);
        }
        return List.copyOf(picked);
    }

    // ------------------------------------------------------------------ 生命周期（3.1）

    /** RUNNING → SUCCEEDED：产物 id 由平台按 (租户, 名称, 尝试次数) 生成，保证可追溯且唯一。 */
    public String succeed(String jobId) {
        TrainingJob job = require(jobId);
        String artifactId = "artifact://" + job.spec().tenant() + "/" + job.spec().name()
                + "/attempt-" + job.attempt();
        job.succeed(tick(), artifactId);
        releaseGpus(job);
        audit.add("任务成功：" + jobId + " → " + artifactId);
        return artifactId;
    }

    /** RUNNING → FAILED：进入终态时立即归还 GPU，池子不能被失败任务长期占着。 */
    public void fail(String jobId, String reason) {
        TrainingJob job = require(jobId);
        job.fail(tick(), reason);
        releaseGpus(job);
        audit.add("任务失败：" + jobId + " attempt=" + job.attempt() + " —— " + reason);
    }

    /** FAILED → QUEUED（attempt+1）；超过上限时 {@link TrainingJob#retry} 会抛 IllegalStateException。 */
    public void retry(String jobId) {
        TrainingJob job = require(jobId);
        job.retry(tick(), "operator");
        audit.add("任务重试：" + jobId + " 进入第 " + job.attempt() + " 次尝试");
    }

    public void cancel(String jobId, String operator) {
        TrainingJob job = require(jobId);
        job.cancel(tick(), operator);
        releaseGpus(job);
        audit.add("任务取消：" + jobId + " by " + operator);
    }

    // ------------------------------------------------------------------ 产物与发布（3.4 / 3.5）

    public ModelVersion registerModel(ModelVersion v) {
        ModelVersion stored = registry.register(v);
        audit.add("模型登记：" + stored.ref());
        return stored;
    }

    public ModelVersion promoteModel(String model, String semver) {
        ModelVersion promoted = registry.promote(model, semver);
        audit.add("模型晋级：" + promoted.ref() + " → PROD");
        return promoted;
    }

    public ModelVersion promoteModel(String model, String semver, double threshold) {
        ModelVersion promoted = registry.promote(model, semver, threshold);
        audit.add("模型晋级：" + promoted.ref() + " → PROD（门槛系数 " + threshold + "）");
        return promoted;
    }

    public InferenceService deployInference(String name, InferenceService.Spec spec, int batchSize) {
        InferenceService svc = new InferenceService(name, spec, batchSize);
        services.put(name, svc);
        audit.add("推理服务发布：" + name + " 初始版本 " + spec.modelVersion() + "（" + spec.replicas() + " 副本）");
        return svc;
    }

    public InferenceService service(String name) {
        InferenceService svc = services.get(name);
        if (svc == null) {
            throw new IllegalArgumentException("未知推理服务：" + name);
        }
        return svc;
    }

    /** 运维一屏：只读聚合视图 + Prometheus 文本指标。 */
    public OpsConsole ops(String serviceName) {
        return new OpsConsole(this, service(serviceName));
    }

    // ------------------------------------------------------------------ 内部

    private TrainingJob require(String jobId) {
        TrainingJob job = jobs.get(jobId);
        if (job == null) {
            throw new IllegalArgumentException("未知任务：" + jobId);
        }
        return job;
    }

    /** 归还 GPU 并把这次持有写进计量账本——释放与记账必须在同一个方法里，否则必然漏账。 */
    private void releaseGpus(TrainingJob job) {
        GpuPool.Allocation released = pool.release(job.jobId());
        if (released != null) {
            meter.record(released.tenant(), released.jobId(), released.gpus(), released.startTs(), now());
        }
    }

    private int allocatedBy(List<String> jobIds) {
        int sum = 0;
        for (String id : jobIds) {
            sum += require(id).spec().gpuCount();
        }
        return sum;
    }

    private long tick() {
        clock += TICK_MS;
        return clock;
    }

    /** 提交结果：accepted=false 时 reason 是可直接展示给用户的可读原因。 */
    public record SubmitResult(String jobId, boolean idempotent, String message) {
        public boolean accepted() {
            return jobId != null;
        }

        public String reason() {
            return accepted() ? "" : message;
        }
    }
}
