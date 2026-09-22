// exercises/sol-01-job-lifecycle/Queued.java —— 已提交、等待调度
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol01 *.java && java -cp /tmp/ph22-sol01 Sol01Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：11/11 PASS）

/** 已提交、等待调度。是从 FAILED 重试回来后唯一允许重新进入的状态。 */
public record Queued() implements JobState {
    @Override public String name() { return "QUEUED"; }
    @Override public String toString() { return name(); }
}
