// exercises/sol-01-job-lifecycle/Succeeded.java —— 执行成功（终态）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol01 *.java && java -cp /tmp/ph22-sol01 Sol01Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：11/11 PASS）

/** 执行成功。终态：不允许再被拉回排队（防止「已完成的任务又被跑一遍」）。 */
public record Succeeded() implements JobState {
    @Override public String name() { return "SUCCEEDED"; }
    @Override public String toString() { return name(); }
}
