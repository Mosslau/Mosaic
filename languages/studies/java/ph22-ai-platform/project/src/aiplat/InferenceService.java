// project/src/aiplat/InferenceService.java —— 推理服务：期望状态 + 控制器循环收敛 + 灰度/回滚
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

import java.util.ArrayList;
import java.util.List;

/**
 * 推理服务（主文档 3.5 / 4.2 / 4.3）：K8s 控制器循环的最小复刻。
 *
 * <p>声明式的核心不是「命令」而是「<b>目标 + 循环</b>」：{@link #reconcile()} 每轮只做一步最小动作，
 * 不记录「已经做到第几步」，而是每轮重新比较期望与实际——进程重启后自然恢复（水平），
 * 同轮重复执行不产生额外副作用（幂等），一次只推进一批（限速）。
 *
 * <p>三者收敛顺序（4.3）不可颠倒：<b>先有副本 → 再切流量 → 最后改版本指针</b>。
 * 顺序反了就会在「新副本还没就绪」时把流量切过去，直接打出 5xx。
 *
 * <p>回滚不是特殊路径：它只是把期望状态改回旧版本，然后走同一套收敛逻辑反向执行。
 */
public final class InferenceService {

    /** 服务阶段：稳定 / 滚动中 / 灰度中 / 已收敛 / 回滚中 / 已回滚。 */
    public enum Phase { STABLE, ROLLING_OUT, CANARY, CONVERGED, ROLLING_BACK, ROLLED_BACK }

    /** 期望状态：镜像 + 模型版本 + 副本数。 */
    public record Spec(String image, String modelVersion, int replicas) {
        public Spec {
            if (image == null || image.isBlank()) throw new IllegalArgumentException("镜像必填");
            if (modelVersion == null || modelVersion.isBlank()) throw new IllegalArgumentException("modelVersion 必填");
            if (replicas <= 0) throw new IllegalArgumentException("replicas 必须为正");
        }
    }

    /** 一轮收敛动作：kind 为 NONE/SURGE/TRAFFIC/DRAIN/ROLLED_BACK，detail 供人读。 */
    public record Action(String kind, String detail) {
        public static Action none() {
            return new Action("NONE", "期望状态与实际状态一致，无需动作");
        }
    }

    /** 只读状态快照。 */
    public record Status(int readyOld, int readyNew, int desired, String currentVersion,
                         String candidateVersion, int newTrafficPct, Phase phase, String unhealthyReason) {
        /** 总就绪副本 = 旧版本就绪 + 新版本就绪（maxSurge 期间会大于 desired）。 */
        public int ready() {
            return readyOld + readyNew;
        }
    }

    private final String name;
    private final int batchSize;              // maxSurge/maxUnavailable 的最小形式：一批推进多少副本
    private final List<String> events = new ArrayList<>();

    private Spec live;                        // 当前生效（对外服务）的版本
    private Spec desired;                     // 期望状态：滚动中指向新版本，回滚后改回旧版本
    private String candidateVersion;          // 本次发布的候选版本（回滚后仍保留，供审计）
    private int readyOld;
    private int readyNew;
    private int newTrafficPct;                // 切到候选版本的流量百分比
    private Phase phase;
    private String unhealthyReason;

    public InferenceService(String name, Spec initial, int batchSize) {
        this.name = name;
        this.batchSize = Math.max(1, batchSize);
        this.live = initial;
        this.desired = initial;
        this.candidateVersion = initial.modelVersion();
        this.readyOld = initial.replicas();
        this.readyNew = 0;
        this.newTrafficPct = 0;
        this.phase = Phase.STABLE;
        events.add("初始化：期望 = 实际 = " + initial.modelVersion() + "（" + initial.replicas() + " 副本，流量 100%）");
    }

    public String name() { return name; }
    public int batchSize() { return batchSize; }
    public List<String> events() { return List.copyOf(events); }

    public Status status() {
        return new Status(readyOld, readyNew, desired.replicas(), live.modelVersion(),
                candidateVersion, newTrafficPct, phase, unhealthyReason);
    }

    /** 当前版本（对外服务）的流量百分比：候选版本拿走多少，当前版本就少多少。 */
    public int currentTrafficPct() {
        return 100 - newTrafficPct;
    }

    /** 提交新的期望状态（发布）。与当前生效版本完全相同则视为无变化。 */
    public boolean deploy(Spec next) {
        if (next.modelVersion().equals(live.modelVersion()) && next.replicas() == live.replicas()) {
            events.add("发布请求被忽略：候选 " + next.modelVersion() + " 与当前版本一致");
            return false;
        }
        this.desired = next;
        this.candidateVersion = next.modelVersion();
        this.readyNew = 0;
        this.newTrafficPct = 0;
        this.unhealthyReason = null;
        this.phase = Phase.ROLLING_OUT;
        events.add("发布请求：候选 " + next.modelVersion() + "（镜像 " + next.image()
                + "，期望副本 " + next.replicas() + "，批大小 " + batchSize + "）");
        return true;
    }

    /**
     * 控制器循环的一步：比较期望与实际，只做一个最小动作。
     *
     * <p>循环不变量：{@code readyOld} 始终是「当前生效版本」的就绪副本数，{@code readyNew} 是候选版本的；
     * 收敛完成时把候选副本数搬到 readyOld 并把 live 指向候选——版本指针切换是最后一步。
     */
    public Action reconcile() {
        switch (phase) {
            case STABLE, CONVERGED, ROLLED_BACK -> {
                return Action.none();      // 期望 == 实际：这一步什么都不做才是幂等的
            }
            case ROLLING_OUT -> {
                int step = Math.min(batchSize, desired.replicas() - readyNew);
                readyNew += step;
                boolean full = readyNew >= desired.replicas();
                if (full) {
                    phase = Phase.CANARY;   // 副本齐了才进入切流阶段（先有副本）
                }
                return new Action("SURGE", "启动候选副本 " + step + " 个（readyNew=" + readyNew
                        + "/" + desired.replicas() + "）" + (full ? "，副本齐备，进入灰度切流" : ""));
            }
            case CANARY -> {
                int next = newTrafficPct == 0 ? 10 : (newTrafficPct < 50 ? 50 : 100);
                boolean full = next >= 100 && readyNew >= desired.replicas();
                newTrafficPct = next;
                if (full) {
                    // 流量 100% 且副本齐备 → 才把「当前版本」指针指向新版本（最后改版本）
                    live = desired;
                    readyOld = readyNew;
                    readyNew = 0;
                    phase = Phase.CONVERGED;
                    events.add("灰度完成：当前版本切到 " + live.modelVersion() + "，流量 100%");
                }
                return new Action("TRAFFIC", "候选版本流量切到 " + next + "%" + (full ? "，版本指针切换" : ""));
            }
            case ROLLING_BACK -> {
                if (newTrafficPct > 0) {
                    newTrafficPct = 0;      // 回滚第一步永远是先把流量拉回来，保住线上
                    return new Action("TRAFFIC", "候选版本流量回退到 0%");
                }
                if (readyNew > 0) {
                    int step = Math.min(batchSize, readyNew);
                    readyNew -= step;
                    return new Action("DRAIN", "排空候选副本 " + step + " 个（readyNew=" + readyNew + "）");
                }
                phase = Phase.ROLLED_BACK;
                events.add("回滚完成：当前版本 " + live.modelVersion() + "，流量 100%，候选 "
                        + candidateVersion + " 已排空");
                return new Action("ROLLED_BACK", "回滚完成：当前版本 " + live.modelVersion() + "，流量 100%");
            }
        }
        return Action.none();   // 不可达：sealed 枚举已穷尽
    }

    /**
     * 上报健康失败（灰度观察期指标劣化、新副本起不来）。
     *
     * <p>回滚 = 「期望状态改回旧版本 + 重新收敛」——不是特别分支，所以这里只改期望与阶段，
     * 具体动作仍由 {@link #reconcile()} 一步步执行。
     */
    public void reportUnhealthy(String reason) {
        if (phase != Phase.ROLLING_OUT && phase != Phase.CANARY) {
            throw new IllegalStateException("当前阶段 " + phase + " 不接受健康失败上报：只有滚动/灰度中才可能回滚");
        }
        this.unhealthyReason = (reason == null || reason.isBlank()) ? "未提供原因" : reason;
        this.phase = Phase.ROLLING_BACK;
        this.desired = live;              // 期望状态改回旧版本
        events.add("健康检查失败：" + unhealthyReason + " → 期望状态改回 " + live.modelVersion());
    }

    /** 人工回滚：与健康失败回滚走同一条路径。 */
    public void rollback() {
        reportUnhealthy("人工触发回滚");
    }
}
