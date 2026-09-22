// exercises/sol-04-release-decision/RolloutAction.java —— 灰度决策器的五种下一步动作
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol04 *.java && java -cp /tmp/ph22-sol04 Sol04Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：13/13 PASS）

/** 决策器对「下一步做什么」的全部答案（回滚不是特殊路径，它只是一次把流量归零并退回 STAGING 的动作）。 */
public enum RolloutAction {

    /** 晋级：STAGING → CANARY，开始 10% 灰度。 */
    PROMOTE,

    /** 灰度推进到 50%。 */
    ADVANCE_50,

    /** 灰度推进到 100%。 */
    ADVANCE_100,

    /** 回滚：流量归零、退回 STAGING（保留旧版本继续服务）。 */
    ROLLBACK,

    /** 保持：指标未达门槛 / 观察期未过 / 已稳定，本轮什么都不做。 */
    HOLD
}
