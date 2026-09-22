// exercises/sol-04-release-decision/Sol04Demo.java —— 练习 4 验收入口：晋级门槛 / 灰度推进 / 失败回滚
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol04 *.java && java -cp /tmp/ph22-sol04 Sol04Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：13/13 PASS）

import java.util.ArrayList;
import java.util.List;

/**
 * 对应 22-ai-platform.md 3.4（晋级门槛）、3.5（灰度与回滚）、4.3（副本→流量→版本三要素收敛）
 * 以及第 7 章练习 4。全部断言只依赖纯函数 decide 的返回值。
 */
public final class Sol04Demo {

    private static final double PROD = 0.85;
    private static final double GOOD = 0.90;
    private static final double BAD = 0.80;

    private static int passed = 0;
    private static int total = 0;

    public static void main(String[] args) {
        // ---- 1) 晋级门槛 ----
        Decision promote = RolloutDecider.decide(Stage.STAGING, GOOD, PROD, true, 0);
        check(promote.action() == RolloutAction.PROMOTE
                        && promote.nextStage() == Stage.CANARY
                        && promote.targetPct() == 10,
                "达标晋级：STAGING + 候选 " + GOOD + " >= 线上 " + PROD + " → " + promote);

        Decision belowGate = RolloutDecider.decide(Stage.STAGING, BAD, PROD, true, 0);
        check(belowGate.action() == RolloutAction.HOLD
                        && belowGate.nextStage() == Stage.STAGING
                        && belowGate.targetPct() == 0
                        && belowGate.reason().contains("晋级门槛"),
                "指标不达标不得晋级：候选 " + BAD + " < 线上 " + PROD + " → 保持不动（" + belowGate.reason() + "）");

        // ---- 2) 健康失败必回滚 ----
        Decision rollbackCanary = RolloutDecider.decide(Stage.CANARY, GOOD, PROD, false, 50);
        check(rollbackCanary.action() == RolloutAction.ROLLBACK
                        && rollbackCanary.nextStage() == Stage.STAGING
                        && rollbackCanary.targetPct() == 0,
                "健康失败必回滚（灰度期）：CANARY@50% + 健康检查失败 → " + rollbackCanary);

        Decision rollbackStaging = RolloutDecider.decide(Stage.STAGING, GOOD, PROD, false, 0);
        check(rollbackStaging.action() == RolloutAction.ROLLBACK && rollbackStaging.targetPct() == 0,
                "健康失败必回滚（未上线）：STAGING 阶段健康失败 → 取消本次发布 " + rollbackStaging.action());

        // ---- 3) 健康则按 10 → 50 → 100 推进 ----
        Decision to50 = RolloutDecider.decide(Stage.CANARY, GOOD, PROD, true, 10);
        check(to50.action() == RolloutAction.ADVANCE_50 && to50.targetPct() == 50
                        && to50.nextStage() == Stage.CANARY,
                "灰度推进 10% → 50%：" + to50.reason());

        Decision to100 = RolloutDecider.decide(Stage.CANARY, GOOD, PROD, true, 50);
        check(to100.action() == RolloutAction.ADVANCE_100 && to100.targetPct() == 100
                        && to100.nextStage() == Stage.CANARY,
                "灰度推进 50% → 100%：" + to100.reason());

        // ---- 4) 100% 后进入稳定态 ----
        Decision stabilize = RolloutDecider.decide(Stage.CANARY, GOOD, PROD, true, 100);
        check(stabilize.action() == RolloutAction.HOLD && stabilize.nextStage() == Stage.STABLE
                        && stabilize.targetPct() == 100,
                "100% 观察期通过进入稳定态：" + stabilize.reason());

        Decision stableIdempotent = RolloutDecider.decide(Stage.STABLE, GOOD, PROD, true, 100);
        check(stableIdempotent.nextStage() == Stage.STABLE && stableIdempotent.targetPct() == 100
                        && RolloutDecider.decide(Stage.STABLE, 0.10, 0.99, false, 100).action() == RolloutAction.HOLD,
                "稳定态幂等保持：STABLE 下无论指标/健康如何都不再变更（已定版）");

        // ---- 5) 灰度期指标劣化回滚 ----
        Decision degraded = RolloutDecider.decide(Stage.CANARY, 0.70, PROD, true, 50);
        check(degraded.action() == RolloutAction.ROLLBACK && degraded.nextStage() == Stage.STAGING
                        && degraded.targetPct() == 0 && degraded.reason().contains("劣化"),
                "灰度期业务指标劣化同样回滚（不只看进程活着）：" + degraded.reason());

        // ---- 6) 非法输入被拒 ----
        boolean pctGuarded = false;
        String pctMessage = "";
        try {
            RolloutDecider.decide(Stage.CANARY, GOOD, PROD, true, 37);
        } catch (IllegalArgumentException e) {
            pctGuarded = true;
            pctMessage = e.getMessage();
        }
        check(pctGuarded && pctMessage.contains("非法流量百分比"),
                "非法百分比输入被拒：" + pctMessage);

        int inconsistentRejected = 0;
        int[][] inconsistent = {{0, 10}, {1, 0}, {2, 50}}; // STAGING@10 / CANARY@0 / STABLE@50
        for (int[] pair : inconsistent) {
            try {
                RolloutDecider.decide(Stage.values()[pair[0]], GOOD, PROD, true, pair[1]);
            } catch (IllegalArgumentException e) {
                if (e.getMessage().contains("阶段与流量不一致")) {
                    inconsistentRejected++;
                }
            }
        }
        check(inconsistentRejected == 3,
                "阶段与流量不一致被拒 " + inconsistentRejected + "/3（STAGING≠0、CANARY=0、STABLE≠100）");

        // ---- 7) 纯函数：同输入两遍结果相等 ----
        check(RolloutDecider.decide(Stage.CANARY, GOOD, PROD, true, 10)
                        .equals(RolloutDecider.decide(Stage.CANARY, GOOD, PROD, true, 10)),
                "纯函数确定性：同一输入跑两遍，Decision 逐字段相等（可复盘、可断言）");

        // ---- 8) 全链路闭环：STAGING → 10 → 50 → 100 → STABLE ----
        Stage stage = Stage.STAGING;
        int pct = 0;
        List<String> trace = new ArrayList<>();
        for (int i = 0; i < 4; i++) {
            Decision step = RolloutDecider.decide(stage, GOOD, PROD, true, pct);
            trace.add(step.action().name());
            stage = step.nextStage();
            pct = step.targetPct();
        }
        check(trace.equals(List.of("PROMOTE", "ADVANCE_50", "ADVANCE_100", "HOLD"))
                        && stage == Stage.STABLE && pct == 100,
                "全链路闭环：STAGING → 10% → 50% → 100% → STABLE，轨迹 " + trace + "，终态 " + stage + "@" + pct + "%");

        System.out.println("发布链路: " + trace + " → " + stage + "@" + pct + "%");
        System.out.println("ALL PASS: " + passed + "/" + total);
        if (passed != total) {
            System.exit(1);
        }
    }

    private static void check(boolean ok, String label) {
        total++;
        if (ok) {
            passed++;
        }
        System.out.println((ok ? "PASS " : "FAIL ") + label);
    }
}
