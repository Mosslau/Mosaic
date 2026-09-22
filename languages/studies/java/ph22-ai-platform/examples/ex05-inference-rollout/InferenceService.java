// languages/java/ph22-ai-platform/examples/ex05-inference-rollout/InferenceService.java —— 推理服务控制器循环：观测实际状态、与期望状态比较、只给出下一步最小动作
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex05 *.java && java -cp /tmp/ph22-ex05 RolloutDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
import java.util.List;

/**
 * 期望状态：一次声明式发布要改的三样东西——镜像、模型版本、副本数——外加两个限速旋钮。
 * maxSurge 限制「最多允许多起几个副本」，maxUnavailable 限制「最少要留几个可用副本」；
 * 缺了这两个上限，收敛就会变成一次性重启全部副本（容量雪崩），而不是「滚动更新」。
 */
record Spec(String image, String modelVersion, int replicas, int maxSurge, int maxUnavailable) {
    Spec {
        if (replicas < 1) {
            throw new IllegalArgumentException("replicas 必须 ≥ 1：" + replicas);
        }
        if (maxSurge < 0 || maxUnavailable < 0) {
            throw new IllegalArgumentException("maxSurge/maxUnavailable 不能为负");
        }
    }
}

/**
 * 实际状态：控制器每一轮**重新观测**到的世界快照。
 * updated 的含义是「已经是期望版本的副本数」（对应 K8s 的 updatedReplicas）——它**相对期望版本**而言：
 * 期望版本一变（例如回滚回 v1），同一批机器重新观测到的 updated 会立刻变成 v1 副本数（本例回滚时为 0）。
 * trafficVersion/trafficPct 描述流量：pct 是 trafficVersion 承载的比例，剩下的走另一个版本。
 */
record Status(int ready, int updated, String trafficVersion, int trafficPct) {
    Status {
        if (ready < 0 || updated < 0 || updated > ready) {
            throw new IllegalArgumentException("必须满足 0 ≤ updated ≤ ready：" + updated + "/" + ready);
        }
        if (trafficPct < 0 || trafficPct > 100) {
            throw new IllegalArgumentException("trafficPct 必须在 [0,100]：" + trafficPct);
        }
    }
}

/**
 * 控制器（reconciler）：没有任何副作用，只回答一个问题——「为了让实际收敛到期望，下一步做哪一个最小动作」。
 * 三个工程纪律都在这里体现：
 *   ① 幂等——纯函数，同一 (spec, status) 永远给同一答案，不记录「已经做到第几步」；
 *   ② 水平——每轮从零重新比较期望与实际，所以进程重启不丢进度；
 *   ③ 限速——一次只给一个动作（一批 ≤ maxSurge / 不低于 maxUnavailable）。
 * 回滚不是特殊代码路径：它同样是「期望状态改回旧版本 + 重新收敛」（见 RolloutDemo 阶段 2）。
 */
public final class InferenceService {

    private InferenceService() { }

    public static List<String> reconcile(Spec spec, Status status) {
        int old = status.ready() - status.updated();

        // 规则 1（回滚）：流量已经处于分裂状态（0<pct<100）却指向非期望版本——说明灰度推进途中期望被改了回去。
        // 要求 updated>0 是 4.3「先有副本、再切流量」的硬约束：期望版本一个可用副本都没有就把流量切过去，
        // 等于直接给用户送 5xx；那种情况先落到规则 2 去补副本，补出副本后这一条才会命中。
        if (status.trafficVersion() != null
                && !status.trafficVersion().equals(spec.modelVersion())
                && status.trafficPct() > 0 && status.trafficPct() < 100
                && status.updated() > 0) {
            return List.of("rollback");
        }

        // 规则 2（起新副本）：期望版本副本还不够，且总量没触到 replicas+maxSurge 的天花板 → 只起一个。
        if (status.updated() < spec.replicas() && status.ready() < spec.replicas() + spec.maxSurge()) {
            return List.of("start-replica");
        }

        // 规则 3（停旧副本）：还有旧版本副本，且停掉一个之后可用副本仍不低于 replicas-maxUnavailable → 只停一个。
        if (old > 0 && status.ready() - 1 >= spec.replicas() - spec.maxUnavailable()) {
            return List.of("stop-old-replica");
        }

        // 规则 4（纯扩容）：没有旧版本可以替换（old==0），单纯是副本数不够。
        if (status.ready() < spec.replicas()) {
            return List.of("start-replica");
        }

        // 规则 5（缩容）：副本数超过期望（缩容，或回滚完成后残留的 v2 副本）→ 停到期望为止。
        if (status.ready() > spec.replicas()) {
            return List.of("stop-old-replica");
        }

        // 规则 6（切流量）：副本全部是期望版本之后才允许动流量，一次一档 10% → 50% → 100%，
        // 档与档之间留给观察期（业务指标劣化就在这一档之间被发现，从而走到规则 1 的回滚）。
        // current 用「流量版本是否等于期望版本」归一：流量还在旧版本上时视作 0%，避免直接跳到 100%。
        int current = spec.modelVersion().equals(status.trafficVersion()) ? status.trafficPct() : 0;
        if (current < 100) {
            int next = current >= 50 ? 100 : (current >= 10 ? 50 : 10);
            return List.of("shift-traffic:" + next);
        }

        // 规则 7（收敛终点）：实际 == 期望——什么都不做。控制器循环必须有这个出口，否则会无限动作。
        return List.of();
    }
}
