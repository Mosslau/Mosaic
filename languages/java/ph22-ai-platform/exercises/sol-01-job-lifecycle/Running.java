// exercises/sol-01-job-lifecycle/Running.java —— 已拿到资源、正在执行
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol01 *.java && java -cp /tmp/ph22-sol01 Sol01Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：11/11 PASS）

/** 已拿到资源、正在执行。只能收敛到 Succeeded / Failed / Cancelled。 */
public record Running() implements JobState {
    @Override public String name() { return "RUNNING"; }
    @Override public String toString() { return name(); }
}
