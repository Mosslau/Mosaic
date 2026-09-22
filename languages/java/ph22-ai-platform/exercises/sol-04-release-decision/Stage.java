// exercises/sol-04-release-decision/Stage.java —— 模型发布阶段（staging → canary → stable）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol04 *.java && java -cp /tmp/ph22-sol04 Sol04Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：13/13 PASS）

/**
 * 发布阶段。灰度期（CANARY）内部再用流量百分比细分 10% → 50% → 100%，
 * 100% 观察期通过后才进入 STABLE（定版）。
 */
public enum Stage {

    /** 候选版本已登记，尚未承接任何线上流量（流量必须为 0%）。 */
    STAGING,

    /** 灰度中，按 10% / 50% / 100% 承接流量。 */
    CANARY,

    /** 已定版，全部流量且版本指针已指向它（流量必须为 100%）。 */
    STABLE
}
