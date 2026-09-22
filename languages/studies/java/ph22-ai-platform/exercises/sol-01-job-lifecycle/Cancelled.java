// exercises/sol-01-job-lifecycle/Cancelled.java —— 人工取消（终态）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol01 *.java && java -cp /tmp/ph22-sol01 Sol01Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：11/11 PASS）

/** 人工取消。终态不可变；reason 记录「谁因为什么把它杀了」的上下文。 */
public record Cancelled(String reason) implements JobState {
    @Override public String name() { return "CANCELLED"; }
    @Override public String toString() { return name(); }
}
