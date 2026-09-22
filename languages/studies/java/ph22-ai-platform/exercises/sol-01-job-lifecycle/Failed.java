// exercises/sol-01-job-lifecycle/Failed.java —— 执行失败（唯一可重试的状态）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol01 *.java && java -cp /tmp/ph22-sol01 Sol01Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：11/11 PASS）

/** 执行失败。失败是唯一可以回到 Queued 的状态，且受 attempt 上限约束。 */
public record Failed(String reason) implements JobState {
    @Override public String name() { return "FAILED"; }
    @Override public String toString() { return name(); }
}
