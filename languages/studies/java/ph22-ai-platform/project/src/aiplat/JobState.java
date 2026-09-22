// project/src/aiplat/JobState.java —— 训练任务状态机（sealed + switch 穷尽）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

/**
 * 任务生命周期状态（主文档 3.1）：sealed 让「状态只有这五种」成为编译期事实。
 *
 * <p>为什么用 sealed 而不是 enum + 字段：每种状态携带的数据不同（QUEUED 只需入队时间，
 * SUCCEEDED 要带产物，FAILED 要带原因），record + sealed 让「SUCCEEDED 一定读得到 artifactId」
 * 成为类型保证，调用方不需要任何强转与 null 检查。
 *
 * <p>合法迁移（其余一律 IllegalStateException，由聚合根 {@link TrainingJob} 执行）：
 * QUEUED → RUNNING | CANCELLED；RUNNING → SUCCEEDED | FAILED | CANCELLED；FAILED → QUEUED（重试）。
 */
public sealed interface JobState
        permits JobState.Queued, JobState.Running, JobState.Succeeded, JobState.Failed, JobState.Cancelled {

    /** 状态名，用于审计文本、指标标签与断言。 */
    String label();

    /**
     * 是否终态（不可再变）。
     *
     * <p>注意 FAILED 返回 false：FAILED 是否终态取决于 attempt 有没有用尽，
     * 只有聚合根知道 attempt，所以这里只声明「本状态自身不终态」，终态判定交给 {@link TrainingJob#isTerminal()}。
     */
    boolean isTerminal();

    /** 已入队、等待调度（可能来自首次提交，也可能来自重试）。 */
    record Queued(long sinceTs) implements JobState {
        @Override public String label() { return "QUEUED"; }
        @Override public boolean isTerminal() { return false; }
    }

    /** 已分配 GPU 并交给执行体，等待状态上报。 */
    record Running(long sinceTs, int attempt) implements JobState {
        @Override public String label() { return "RUNNING"; }
        @Override public boolean isTerminal() { return false; }
    }

    /** 成功终态：必须带产物（artifactId 是模型血缘的锚点）。 */
    record Succeeded(long ts, String artifactId, int attempt) implements JobState {
        @Override public String label() { return "SUCCEEDED"; }
        @Override public boolean isTerminal() { return true; }
    }

    /** 失败：可重试（attempt 未用尽）或已成终态（attempt 用尽）。 */
    record Failed(long ts, String reason, int attempt) implements JobState {
        @Override public String label() { return "FAILED"; }
        @Override public boolean isTerminal() { return false; }
    }

    /** 人工取消终态：审计里记下是谁杀的。 */
    record Cancelled(long ts, String operator) implements JobState {
        @Override public String label() { return "CANCELLED"; }
        @Override public boolean isTerminal() { return true; }
    }
}
