// languages/java/ph22-ai-platform/examples/ex01-training-job/TrainingJob.java —— 训练任务聚合根：状态机 + 幂等键 + 审计轨迹
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex01 *.java && java -cp /tmp/ph22-ex01 TrainingJobDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
//
// 为什么把这些规则收在聚合根里，而不是散在 Service：
//   ① 终态不可变、重试上限、迁移合法性是「任务这个东西」自身的不变式，放在聚合外
//      迟早会被某个新调用方绕过；放在聚合内则非法操作只能抛异常，挡在数据之外。
//   ② 每次迁移都产出一条审计条目——值班第一问永远是「谁把任务杀了」，审计必须是
//      状态迁移的副产物而不是靠调用方自觉补写。
//   ③ 重试上限 3 意味着最多 3 次 attempt（首次 + 2 次重试）；无上限重试会吃掉整个池子。
import java.util.ArrayList;
import java.util.List;

public final class TrainingJob {
    /** 尝试次数上限：首次 attempt=1，因此最多允许 2 次 retry()。 */
    public static final int MAX_ATTEMPT = 3;

    private final String id;
    private final JobSpec spec;
    private final String idempotencyKey;
    private final List<AuditEntry> audit = new ArrayList<>();

    private JobState state;
    private int attempt;

    TrainingJob(String id, JobSpec spec) {
        this.id = id;
        this.spec = spec;
        this.idempotencyKey = spec.tenant() + "/" + spec.name() + "/" + spec.contentHash();
        this.attempt = 1;
        this.state = new JobState.Queued();
        // 建单本身也是一次状态迁移（null → QUEUED），这样审计条数恰好等于迁移次数
        this.audit.add(AuditEntry.of(null, "Queued", "submit", "client"));
    }

    /** 一次状态迁移的审计条目：(ts, from, to, reason, operator)。 */
    public record AuditEntry(long ts, String from, String to, String reason, String operator) {
        static AuditEntry of(String from, String to, String reason, String operator) {
            return new AuditEntry(System.currentTimeMillis(), from, to, reason, operator);
        }
    }

    // ---- 领域方法：每一个都是一次受约束的状态迁移 ----

    /** QUEUED → RUNNING：只有排到队的任务才能开始跑。 */
    public void start(String node) {
        transition(new JobState.Running(node), "schedule->" + node, "scheduler");
    }

    /** RUNNING → SUCCEEDED（终态）：产物 id 由执行体上报。 */
    public void succeed(String artifactId) {
        transition(new JobState.Succeeded(artifactId), "artifact=" + artifactId, "executor");
    }

    /** RUNNING → FAILED：失败可重试，因此不是终态。 */
    public void fail(String reason) {
        transition(new JobState.Failed(reason), reason, "executor");
    }

    /**
     * FAILED → QUEUED：重试。
     * 只允许从 FAILED 重试（RUNNING 重试会让两个执行体同时写同一个产物），
     * 且 attempt 上限为 MAX_ATTEMPT。
     */
    public void retry(String operator) {
        require(state instanceof JobState.Failed,
                "retry 只允许 FAILED 状态，当前=" + stateName());
        require(attempt < MAX_ATTEMPT,
                "重试次数已达上限 " + MAX_ATTEMPT + " 次(当前 attempt=" + attempt + ")");
        require(!isTerminal(), "终态不可重试");
        attempt++;
        transition(new JobState.Queued(), "retry#" + attempt, operator);
    }

    /** QUEUED / RUNNING → CANCELLED（终态）：人主动终止，必须留操作人。 */
    public void cancel(String operator) {
        require(!isTerminal(), "终态不可取消，" + stateName() + " 已是终态");
        transition(new JobState.Cancelled(operator), "cancel-by-" + operator, operator);
    }

    // ---- 状态机核心：合法性判定 + 审计写入集中在一个出口 ----

    private void transition(JobState next, String reason, String operator) {
        require(legal(state, next),
                "非法状态迁移 " + stateName() + " → " + next.getClass().getSimpleName());
        require(!isTerminal(), stateName() + " 是终态，不可再迁移");
        String from = stateName();
        state = next;
        audit.add(AuditEntry.of(from, stateName(), reason, operator));
    }

    /**
     * 合法迁移表（其余一律 IllegalStateException）：
     *   QUEUED  → RUNNING | CANCELLED
     *   RUNNING → SUCCEEDED | FAILED | CANCELLED
     *   FAILED  → QUEUED（重试，attempt+1）
     * SUCCEEDED / CANCELLED 是终态，无出边。
     */
    private static boolean legal(JobState from, JobState to) {
        if (from instanceof JobState.Queued) {
            return to instanceof JobState.Running || to instanceof JobState.Cancelled;
        }
        if (from instanceof JobState.Running) {
            return to instanceof JobState.Succeeded
                    || to instanceof JobState.Failed
                    || to instanceof JobState.Cancelled;
        }
        if (from instanceof JobState.Failed) {
            return to instanceof JobState.Queued;
        }
        return false;
    }

    public boolean isTerminal() {
        return state instanceof JobState.Succeeded || state instanceof JobState.Cancelled;
    }

    /**
     * 当前状态的可读名（写审计用）。
     * 这里用 Java 17 稳定的 instanceof 模式匹配；sealed 的穷尽性检查在 switch 表达式 /
     * 模式 switch 里才有，而模式 switch 是 Java 21 特性，本阶段基线是 17。
     */
    public String stateName() {
        if (state instanceof JobState.Queued) {
            return "Queued";
        }
        if (state instanceof JobState.Running) {
            return "Running";
        }
        if (state instanceof JobState.Succeeded) {
            return "Succeeded";
        }
        if (state instanceof JobState.Failed) {
            return "Failed";
        }
        if (state instanceof JobState.Cancelled) {
            return "Cancelled";
        }
        throw new IllegalStateException("未知状态: " + state.getClass());
    }

    private static void require(boolean ok, String message) {
        if (!ok) {
            throw new IllegalStateException("非法迁移: " + message);
        }
    }

    // ---- 只读访问器：状态只能经上面的领域方法改变，没有 setter ----

    public String id() { return id; }
    public JobSpec spec() { return spec; }
    public JobState state() { return state; }
    public int attempt() { return attempt; }
    public String idempotencyKey() { return idempotencyKey; }

    /** 返回副本，防止外部直接改审计列表。 */
    public List<AuditEntry> audit() { return List.copyOf(audit); }
}
