// exercises/sol-01-job-lifecycle/AuditEntry.java —— 状态迁移审计条目（不可变）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol01 *.java && java -cp /tmp/ph22-sol01 Sol01Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：11/11 PASS）

import java.time.Instant;

/**
 * 「谁在什么时候把任务从哪个状态改到了哪个状态、为什么」——值班第一问的答案。
 * seq 单调递增，恰好等于该任务成功迁移的次数（失败/被拒的迁移不写审计）。
 */
public record AuditEntry(long seq, Instant at, String from, String to, String reason, String operator) {
}
