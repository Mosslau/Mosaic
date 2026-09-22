// exercises/sol-04-release-decision/Decision.java —— 决策结果（动作 + 下一阶段 + 目标流量 + 可读原因）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol04 *.java && java -cp /tmp/ph22-sol04 Sol04Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：13/13 PASS）

/**
 * 一次灰度决策的完整结果。record 的 equals 是逐字段比较，
 * 因此「同一输入两遍决策结果相等」可以直接断言（纯函数性质）。
 */
public record Decision(RolloutAction action, Stage nextStage, int targetPct, String reason) {

    public Decision {
        if (action == null || nextStage == null) {
            throw new IllegalArgumentException("动作与下一阶段不能为空");
        }
        if (targetPct < 0 || targetPct > 100) {
            throw new IllegalArgumentException("目标流量百分比越界：" + targetPct);
        }
    }

    @Override
    public String toString() {
        return action + " → " + nextStage + " @" + targetPct + "% :: " + reason;
    }
}
