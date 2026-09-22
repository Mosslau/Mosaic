// languages/java/ph22-ai-platform/examples/ex05-inference-rollout/RolloutDemo.java —— 滚动更新 / 灰度切流 / 失败回滚的确定性演练（同一份控制器代码走完全程）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex05 *.java && java -cp /tmp/ph22-ex05 RolloutDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class RolloutDemo {

    public static void main(String[] args) {
        AtomicInteger pass = new AtomicInteger();
        int total = 7;

        // ---------- 数据（确定性自造）：v1 → v2 滚动更新，4 副本，最多多起 1 个、最少保留 3 个可用 ----------
        Spec rollout = new Spec("registry.local/ranker:v2", "v2", 4, 1, 1);
        Status initial = new Status(4, 0, "v1", 100);

        List<String> trace = new ArrayList<>();
        Sim sim = new Sim(rollout, initial);

        int maxReady = initial.ready();
        int minReady = initial.ready();
        int maxStartRun = 0;
        int startRun = 0;
        int firstShiftAtUpdated = -1;
        boolean shiftBeforeReady = false;

        // ---------- 阶段 1：滚动更新推进到灰度 50% ----------
        while (true) {
            Status before = sim.status();
            String action = sim.step();
            if (action == null) {
                break;
            }
            trace.add(action);
            maxReady = Math.max(maxReady, Math.max(before.ready(), sim.status().ready()));
            minReady = Math.min(minReady, Math.min(before.ready(), sim.status().ready()));
            if (action.equals("start-replica")) {
                startRun++;
                maxStartRun = Math.max(maxStartRun, startRun);
            } else {
                startRun = 0;
            }
            if (action.startsWith("shift-traffic")) {
                if (firstShiftAtUpdated < 0) {
                    firstShiftAtUpdated = before.updated();
                }
                if (before.updated() < rollout.replicas()) {
                    shiftBeforeReady = true;
                }
            }
            if (action.equals("shift-traffic:50")) {
                break;   // 灰度到 50%，下一轮「健康检查失败」
            }
        }
        List<String> forwardTrace = List.copyOf(trace);

        // ---------- 阶段 2：灰度 50% 时健康检查失败 → 期望状态改回 v1 ----------
        // 回滚不改控制器，只改期望：平台把 Spec 的 modelVersion 指回 v1，剩下的仍交给同一个 reconcile。
        Spec rollback = new Spec("registry.local/ranker:v1", "v1", 4, 1, 1);
        Status beforeRollback = sim.status();
        // updated 是「已是期望版本」的副本数；期望从 v2 改回 v1 后重新观测，v1 副本数 = 0。
        Status observed = new Status(beforeRollback.ready(), 0, beforeRollback.trafficVersion(), beforeRollback.trafficPct());
        int rollbackAtTrafficPct = observed.trafficPct();

        sim = new Sim(rollback, observed);
        List<String> rollbackPhase = new ArrayList<>();
        boolean rollbackSeen = false;
        boolean rollbackAfterCapacity = false;
        int rollbackIndex = -1;
        int updatedWhenRollback = -1;
        while (true) {
            Status before = sim.status();
            String action = sim.step();
            if (action == null) {
                break;
            }
            rollbackPhase.add(action);
            trace.add(action);
            if (action.equals("rollback")) {
                rollbackSeen = true;
                rollbackIndex = trace.size() - 1;
                updatedWhenRollback = before.updated();
                rollbackAfterCapacity = before.updated() > 0;
            }
        }
        Status settled = sim.status();

        // ---------- 输出：让读者直接看到控制器给出的动作序列 ----------
        System.out.println("滚动更新动作序列（v1→v2）：" + forwardTrace);
        System.out.println("回滚与再收敛动作序列    ：" + rollbackPhase);
        System.out.println("终态：" + settled);

        // 1) 滚动更新分批推进：ready 不越过 replicas+maxSurge，也不跌破 replicas-maxUnavailable
        check(pass, maxStartRun <= rollout.maxSurge()
                        && maxReady <= rollout.replicas() + rollout.maxSurge()
                        && minReady >= rollout.replicas() - rollout.maxUnavailable(),
                "滚动更新分批限速：ready 始终落在 [3,5]，每批新增副本 ≤ maxSurge=1（实测 maxReady=" + maxReady
                        + "，单批最多连续起 " + maxStartRun + " 个）");

        // 2) 新副本没就绪之前，一次流量也不许切（4.3 的顺序：先有副本，再切流量）
        check(pass, !shiftBeforeReady && firstShiftAtUpdated == rollout.replicas(),
                "新副本未就绪不切流量：第一次 shift-traffic 发生在 updated=" + firstShiftAtUpdated + " == replicas=4");

        // 3) 灰度 50% 时健康失败 → 期望改回 v1 → 返回 rollback，且此前已补出 v1 可用副本
        check(pass, rollbackSeen && rollbackAtTrafficPct == 50 && "v2".equals(observed.trafficVersion())
                        && rollbackAfterCapacity,
                "灰度 10%→50% 后健康失败 → 回滚：v2 承载 50% 流量时返回 rollback，且回滚前已补出 v1 可用副本（updated="
                        + updatedWhenRollback + "）");

        // 4) 回滚后副本数收敛到期望：4 个 v1 就绪、流量 100% 在 v1
        check(pass, settled.ready() == 4 && settled.updated() == 4
                        && "v1".equals(settled.trafficVersion()) && settled.trafficPct() == 100,
                "回滚后副本数收敛到期望：ready=4 updated=4 流量=100% v1");

        // 5) 终态：实际 == 期望 → 空动作（控制器不能无限动作）
        check(pass, InferenceService.reconcile(rollback, settled).isEmpty(),
                "终态（实际 == 期望）reconcile 返回空动作");

        // 6) 幂等：同一输入重复调用结果一致，且不修改输入（纯函数，无副作用重复）
        List<String> a1 = InferenceService.reconcile(rollout, initial);
        List<String> a2 = InferenceService.reconcile(rollout, initial);
        List<String> a3 = InferenceService.reconcile(
                new Spec(rollout.image(), rollout.modelVersion(), rollout.replicas(), rollout.maxSurge(), rollout.maxUnavailable()),
                new Status(initial.ready(), initial.updated(), initial.trafficVersion(), initial.trafficPct()));
        check(pass, a1.equals(a2) && a2.equals(a3) && a1.equals(List.of("start-replica"))
                        && initial.ready() == 4 && initial.updated() == 0 && initial.trafficPct() == 100,
                "同一输入重复 reconcile 幂等：三次调用结果一致，输入状态未被改动");

        // 7) 回滚不是特殊路径：动作词表固定，且 rollback 之后仍用同一套 start/stop 阶梯收敛旧版本副本
        boolean knownVerbs = trace.stream()
                .map(a -> a.split(":")[0])
                .allMatch(v -> List.of("start-replica", "stop-old-replica", "shift-traffic", "rollback").contains(v));
        List<String> afterRollback = trace.subList(rollbackIndex + 1, trace.size());
        check(pass, knownVerbs && afterRollback.contains("start-replica") && afterRollback.contains("stop-old-replica"),
                "回滚不是特殊路径：全程只有 4 个动词，rollback 之后仍走 start/stop 副本收敛");

        System.out.printf("ALL PASS: %d/%d%n", pass.get(), total);
        if (pass.get() != total) {
            System.exit(1);
        }
    }

    /**
     * 极简「执行器」：真实平台里这份工作由 kubelet / 服务网格完成——把控制器给出的一个动作作用到实际状态上，
     * 于是下一轮 reconcile 就能读到新的实际状态。示例里它同时充当「集群」，让整个收敛过程可复现。
     */
    private static final class Sim {
        private final Spec spec;
        private Status status;

        Sim(Spec spec, Status status) {
            this.spec = spec;
            this.status = status;
        }

        Status status() {
            return status;
        }

        /** 走一轮控制器循环；返回 null 表示实际 == 期望（已收敛）。 */
        String step() {
            List<String> next = InferenceService.reconcile(spec, status);
            if (next.isEmpty()) {
                return null;
            }
            String action = next.get(0);
            status = apply(spec, status, action);
            return action;
        }

        private static Status apply(Spec spec, Status st, String action) {
            String verb = action.contains(":") ? action.substring(0, action.indexOf(':')) : action;
            return switch (verb) {
                // 新起的副本一定跑期望版本，所以 ready 与 updated 同时 +1
                case "start-replica" -> new Status(st.ready() + 1, st.updated() + 1, st.trafficVersion(), st.trafficPct());
                // 停副本：若当前副本全是期望版本，这是缩容（updated 一起减）；否则停掉的是旧版本副本
                case "stop-old-replica" -> st.updated() == st.ready()
                        ? new Status(st.ready() - 1, st.updated() - 1, st.trafficVersion(), st.trafficPct())
                        : new Status(st.ready() - 1, st.updated(), st.trafficVersion(), st.trafficPct());
                case "shift-traffic" -> new Status(st.ready(), st.updated(), spec.modelVersion(),
                        Integer.parseInt(action.substring(action.indexOf(':') + 1)));
                case "rollback" -> new Status(st.ready(), st.updated(), spec.modelVersion(), 100);
                default -> throw new IllegalArgumentException("未知动作：" + action);
            };
        }
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
