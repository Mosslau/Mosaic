// exercises/sol-04-release-decision/RolloutDecider.java —— 晋级门槛 + 灰度推进 + 失败回滚（纯函数决策器）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol04 *.java && java -cp /tmp/ph22-sol04 Sol04Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：13/13 PASS）

import java.util.Objects;
import java.util.Set;

/**
 * 模型灰度发布决策器（对应 22-ai-platform.md 3.4 晋级门槛 / 3.5 灰度与回滚 / 4.3 三要素收敛）。
 *
 * 纪律：**先有副本、再切流量、最后改版本**。所以本决策器只在「健康检查通过 + 业务指标不劣于线上」
 * 时才推进流量；任一条件不满足就回滚或保持——绝不在不健康的基础上继续放大流量。
 */
public final class RolloutDecider {

    /** 合法流量百分比：0%（未切流）、10%、50%、100%。 */
    public static final Set<Integer> VALID_PCTS = Set.of(0, 10, 50, 100);

    private RolloutDecider() {
    }

    /**
     * @param stage          当前阶段
     * @param candidateMetric 候选版本业务指标（越大越好）
     * @param prodMetric      当前线上版本指标（晋级门槛基准）
     * @param healthOk        健康检查是否通过
     * @param currentPct      当前流量百分比（只能是 0/10/50/100）
     * @return 下一步动作
     */
    public static Decision decide(Stage stage, double candidateMetric, double prodMetric,
                                  boolean healthOk, int currentPct) {
        Objects.requireNonNull(stage, "stage 不能为空");
        if (!VALID_PCTS.contains(currentPct)) {
            throw new IllegalArgumentException(
                    "非法流量百分比：" + currentPct + "（合法值：0/10/50/100）");
        }
        if (!Double.isFinite(candidateMetric) || candidateMetric < 0) {
            throw new IllegalArgumentException("非法候选指标：" + candidateMetric);
        }
        if (!Double.isFinite(prodMetric) || prodMetric < 0) {
            throw new IllegalArgumentException("非法线上指标：" + prodMetric);
        }
        if (stage == Stage.STAGING && currentPct != 0) {
            throw new IllegalArgumentException("阶段与流量不一致：STAGING 未切流，流量必须为 0%，当前 " + currentPct + "%");
        }
        if (stage == Stage.CANARY && currentPct == 0) {
            throw new IllegalArgumentException("阶段与流量不一致：CANARY 必须已切流（10/50/100），当前 0%");
        }
        if (stage == Stage.STABLE && currentPct != 100) {
            throw new IllegalArgumentException("阶段与流量不一致：STABLE 必须 100% 流量，当前 " + currentPct + "%");
        }

        // 稳定态：已定版，决策器不再做任何变更（幂等保持）。
        if (stage == Stage.STABLE) {
            return new Decision(RolloutAction.HOLD, Stage.STABLE, 100,
                    "已处于稳定态：流量 100%，版本已定版，无需变更");
        }

        // 健康失败：一律回滚（先保线上，再谈发布）。STAGING 回滚 = 取消本次发布。
        if (!healthOk) {
            return new Decision(RolloutAction.ROLLBACK, Stage.STAGING, 0,
                    "健康检查失败：回滚并归零流量（当前 " + currentPct + "%）");
        }

        if (stage == Stage.STAGING) {
            if (candidateMetric < prodMetric) {
                return new Decision(RolloutAction.HOLD, Stage.STAGING, 0,
                        String.format("未达晋级门槛：候选 %.4f < 线上 %.4f，不得开始灰度", candidateMetric, prodMetric));
            }
            return new Decision(RolloutAction.PROMOTE, Stage.CANARY, 10,
                    String.format("达到晋级门槛（%.4f >= %.4f）：开始 10%% 灰度", candidateMetric, prodMetric));
        }

        // CANARY：灰度期指标劣化同样回滚（不只是「进程活着」就算成功）。
        if (candidateMetric < prodMetric) {
            return new Decision(RolloutAction.ROLLBACK, Stage.STAGING, 0,
                    String.format("灰度期指标劣化（候选 %.4f < 线上 %.4f）：回滚", candidateMetric, prodMetric));
        }
        return switch (currentPct) {
            case 10 -> new Decision(RolloutAction.ADVANCE_50, Stage.CANARY, 50, "10% 观察期通过：推进到 50%");
            case 50 -> new Decision(RolloutAction.ADVANCE_100, Stage.CANARY, 100, "50% 观察期通过：推进到 100%");
            case 100 -> new Decision(RolloutAction.HOLD, Stage.STABLE, 100, "100% 观察期通过：转入稳定态");
            default -> throw new IllegalStateException("不可达的流量百分比：" + currentPct);
        };
    }
}
