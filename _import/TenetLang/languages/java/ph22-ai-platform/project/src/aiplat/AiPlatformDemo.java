// project/src/aiplat/AiPlatformDemo.java —— AI 平台最小控制面端到端演示 + 14 项验收断言
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 阶段项目验收：一条完整闭环，全部数据确定性自造（固定时钟 T0 / 确定性逻辑时钟），无外部依赖。
 *
 * <pre>
 * A 提交与配额(1-2) → B 调度策略(3-4) → C 算力台账(5) → D 生命周期与重试(6-8)
 *   → E 模型登记与晋级(9-11) → F 推理服务灰度与回滚(12-13) → G 运维一屏与指标(14)
 * </pre>
 */
public final class AiPlatformDemo {

    /** 固定提交时间基准：2023-11-14T22:13:20Z，保证提交序与审计时间戳可复现。 */
    private static final long T0 = 1_700_000_000_000L;

    public static void main(String[] args) {
        System.out.println("== AI 平台最小控制面（aiplat）闭环演示：提交→调度→生命周期→产物→灰度发布→运维一屏 ==");

        // 控制面装配：8 卡共享池 + 优先级策略；三种租户配额
        AiPlatform plat = new AiPlatform(8, new PriorityPolicy());
        plat.quotaGuard().set("cv", new Quota(8, 6, 5_000_000L));
        plat.quotaGuard().set("nlp", new Quota(4, 3, 500_000L));
        plat.quotaGuard().set("edge", new Quota(2, 1, 10_000L));

        AtomicInteger pass = new AtomicInteger();

        // ================= A. 多租户提交：幂等 + 配额（3.1 / 3.7） =================

        // ① 幂等：同一业务定义的第二次提交返回原任务。故意换掉 submitTs —— 客户端重发时间戳几乎必然变化
        JobSpec detectorSpec = new JobSpec("cv", "detector", 4, 1, 60, T0 + 1_000);
        AiPlatform.SubmitResult r1 = plat.submit(detectorSpec);
        AiPlatform.SubmitResult r1Again = plat.submit(new JobSpec("cv", "detector", 4, 1, 60, T0 + 90_000));
        check(pass, r1.accepted() && r1Again.idempotent() && r1.jobId().equals(r1Again.jobId()) && plat.jobCount() == 1,
                "幂等：同一 (租户,名称,规格) 重复提交返回同一任务 " + r1.jobId()
                        + "，重发时间戳变化不影响幂等键，队列未新增任务");

        // ② 配额：单任务卡数超上限 → 拒绝且原因可读，不静默排队
        AiPlatform.SubmitResult rejected = plat.submit(new JobSpec("edge", "edge-ocr", 4, 5, 30, T0 + 2_000));
        check(pass, !rejected.accepted() && rejected.reason().contains("配额不足")
                        && rejected.reason().contains("4/2") && plat.jobCount() == 1,
                "配额：租户 edge 单任务 4 卡超上限 2 卡 → 拒绝（" + rejected.reason() + "），未进入队列");

        AiPlatform.SubmitResult r2 = plat.submit(new JobSpec("cv", "segmenter", 2, 9, 30, T0 + 3_000));
        AiPlatform.SubmitResult r3 = plat.submit(new JobSpec("cv", "classifier", 2, 5, 45, T0 + 4_000));
        String j1 = r1.jobId();
        String j2 = r2.jobId();
        String j3 = r3.jobId();

        // ================= B. 调度策略：优先级 / FIFO / 回填（3.3 / 4.1） =================

        // ③ 优先级：同一队列，优先级 9>5>1 决策与 FIFO（提交序）不同，但各自确定
        List<Policy.Candidate> queue = plat.queueSnapshot();
        List<String> fifoPick = new FifoPolicy().select(queue, 8);
        List<String> prioPick = new PriorityPolicy().select(queue, 8);
        check(pass, prioPick.equals(List.of(j2, j3, j1)) && fifoPick.equals(List.of(j1, j2, j3))
                        && prioPick.equals(new PriorityPolicy().select(queue, 8)),
                "调度：同一队列按优先级 9>5>1 决策为 " + prioPick + "，FIFO 为 " + fifoPick
                        + "（同输入重放决策完全相同）");

        // ④ 回填：队头 8 卡大任务阻塞 4 卡空闲时，放行 15 分钟的小任务，空闲卡被真正利用
        GpuPool scratch = new GpuPool(4);
        JobSpec bigTrain = new JobSpec("cv", "big-train", 8, 9, 120, T0 + 5_000);
        JobSpec smallFt = new JobSpec("cv", "small-ft", 2, 1, 15, T0 + 6_000);
        List<Policy.Candidate> blockedQueue = List.of(
                new Policy.Candidate("big-train", bigTrain, bigTrain.submitTs()),
                new Policy.Candidate("small-ft", smallFt, smallFt.submitTs()));
        List<String> backfilled = new BackfillPolicy(30).select(blockedQueue, scratch.free());
        List<String> noBackfill = new PriorityPolicy().select(blockedQueue, scratch.free());
        for (String id : backfilled) {
            JobSpec picked = id.equals("small-ft") ? smallFt : bigTrain;
            scratch.tryAllocate(id, picked.tenant(), picked.gpuCount(), T0);
        }
        check(pass, backfilled.equals(List.of("small-ft")) && noBackfill.isEmpty()
                        && scratch.allocatedGpus() == 2 && scratch.free() == 2 && scratch.invariantHolds(),
                "回填：队头 8 卡大任务阻塞时纯优先级一个都不放行，回填放行 15 分钟小任务（空闲卡 4→2，利用率 0%→50%）");

        // ================= C. 算力台账不变量（3.2） =================

        // ⑤ 一轮调度占满 8 卡，账本不变量在分配后仍然成立；超量申请被拒且不污染台账
        List<String> scheduled = plat.schedule();
        check(pass, scheduled.equals(List.of(j2, j3, j1)) && plat.pool().invariantHolds()
                        && plat.pool().allocatedGpus() == 8 && plat.pool().free() == 0
                        && !plat.pool().tryAllocate("oversized", "cv", 1, T0) && plat.pool().invariantHolds()
                        && plat.pool().tenantUsage().getOrDefault("cv", 0) == 8,
                "算力池：调度占满 8 卡后不变量 allocated + free == total 成立，超量申请被拒且账本不变（租户 cv 占用 8）");

        // ================= D. 生命周期推进：成功 / 重试 / 重试上限（3.1） =================

        // ⑥ RUNNING → SUCCEEDED 并产出 artifactId，终态不可变，GPU 立即归还
        String artifact1 = plat.succeed(j1);
        TrainingJob job1 = plat.job(j1).orElseThrow();
        check(pass, job1.state() instanceof JobState.Succeeded s1 && s1.artifactId().equals(artifact1)
                        && artifact1.startsWith("artifact://cv/detector/") && job1.isTerminal()
                        && plat.pool().free() == 4,
                "生命周期：" + j1 + " RUNNING→SUCCEEDED，产出 " + artifact1 + "，GPU 归还（free=4）");

        // ⑦ 第 1 次尝试失败 → 重试为第 2 次尝试后成功
        plat.fail(j2, "CUDA OOM at step 1200");
        plat.retry(j2);
        plat.schedule();
        String artifact2 = plat.succeed(j2);
        TrainingJob job2 = plat.job(j2).orElseThrow();
        check(pass, job2.attempt() == 2 && job2.state().label().equals("SUCCEEDED")
                        && job2.artifactId().equals(artifact2) && job2.audit().size() >= 5,
                "失败重试：" + j2 + " 第 1 次尝试失败 → 重试后第 2 次尝试成功（attempt=" + job2.attempt()
                        + "，审计 " + job2.audit().size() + " 条）");

        // ⑧ 连续 3 次失败 → attempt 用尽 → FAILED 终态，再重试被拒
        plat.fail(j3, "node preempted");
        plat.retry(j3);
        plat.schedule();
        plat.fail(j3, "node preempted");
        plat.retry(j3);
        plat.schedule();
        plat.fail(j3, "node preempted");
        TrainingJob job3 = plat.job(j3).orElseThrow();
        boolean retryRefused = false;
        String refuseReason = "";
        try {
            plat.retry(j3);
        } catch (IllegalStateException e) {
            retryRefused = true;
            refuseReason = e.getMessage();
        }
        check(pass, job3.attempt() == TrainingJob.MAX_ATTEMPTS && job3.state().label().equals("FAILED")
                        && job3.isTerminal() && !job3.canRetry() && retryRefused && plat.pool().free() == 8,
                "重试上限：" + j3 + " 第 3 次尝试仍失败 → FAILED 终态，再重试被拒（" + refuseReason + "），GPU 全部归还");

        // ================= E. 产物登记：血缘 / 禁止倒退 / 晋级门槛（3.4 / 3.6） =================

        DatasetVersion.Ledger datasets = plat.datasets();
        datasets.register(new DatasetVersion("nlp-corpus", "1.0.0", "sha256:9f2c41d0ab", 1_200_000, "data-team"));
        ModelRegistry reg = plat.registry();
        reg.register(new ModelVersion("detector", 1, 0, 0, ModelVersion.Stage.STAGING,
                "nlp-corpus:1.0.0", artifact1, 0.810));
        reg.register(new ModelVersion("detector", 1, 1, 0, ModelVersion.Stage.STAGING,
                "nlp-corpus:1.0.0", artifact2, 0.860));
        reg.register(new ModelVersion("detector", 1, 2, 0, ModelVersion.Stage.STAGING,
                "nlp-corpus:1.0.0", artifact2, 0.700));

        // ⑨ 血缘缺失被拒 + 数据集快照校验（篡改/未知版本一律不通过）
        boolean lineageRejected = false;
        String lineageMsg = "";
        try {
            reg.register(new ModelVersion("detector", 1, 3, 0, ModelVersion.Stage.STAGING,
                    "   ", artifact2, 0.900));
        } catch (IllegalStateException e) {
            lineageRejected = true;
            lineageMsg = e.getMessage();
        }
        check(pass, lineageRejected && lineageMsg.contains("血缘")
                        && datasets.verifySnapshot("nlp-corpus", "1.0.0", "sha256:9f2c41d0ab")
                        && !datasets.verifySnapshot("nlp-corpus", "1.0.0", "sha256:tampered")
                        && !datasets.verifySnapshot("nlp-corpus", "9.9.9", "sha256:9f2c41d0ab"),
                "血缘：数据集版本为空的登记被拒（" + lineageMsg + "）；快照校验和一致才可复现，篡改与未知版本都不通过");

        // ⑩ 版本倒退被拒：已登记 1.2.0 后不能再登记 1.0.5
        boolean regressionRejected = false;
        String regressionMsg = "";
        try {
            reg.register(new ModelVersion("detector", 1, 0, 5, ModelVersion.Stage.STAGING,
                    "nlp-corpus:1.0.0", artifact1, 0.820));
        } catch (IllegalStateException e) {
            regressionRejected = true;
            regressionMsg = e.getMessage();
        }
        check(pass, regressionRejected && regressionMsg.contains("版本倒退") && reg.versions("detector").size() == 3,
                "版本台账：" + regressionMsg + "；登记表仍为 3 条（1.0.0 / 1.1.0 / 1.2.0），倒挂版本未污染台账");

        // ⑪ 晋级门槛：指标劣于 PROD 被拒；达标者晋级且 PROD 全局唯一
        reg.promote("detector", "1.0.0");                       // 首个 PROD
        boolean gateRejected = false;
        String gateMsg = "";
        try {
            reg.promote("detector", "1.2.0");                   // 0.700 < 0.810
        } catch (IllegalStateException e) {
            gateRejected = true;
            gateMsg = e.getMessage();
        }
        ModelVersion promoted = reg.promote("detector", "1.1.0");   // 0.860 >= 0.810
        check(pass, gateRejected && gateMsg.contains("晋级被拒") && promoted.stage() == ModelVersion.Stage.PROD
                        && reg.production("detector").orElseThrow().semver().equals("1.1.0")
                        && reg.countStage(ModelVersion.Stage.PROD) == 1
                        && reg.countStage(ModelVersion.Stage.ARCHIVED) == 1,
                "晋级：" + gateMsg + "；1.1.0（0.860）晋级成功，1.0.0 自动归档，PROD 全局唯一");

        // ================= F. 推理服务：滚动收敛 / 灰度回滚（3.5 / 4.2 / 4.3） =================

        InferenceService svc = plat.deployInference("detector-svc",
                new InferenceService.Spec("aiplat/detector:1.0.0", "1.0.0", 6), 2);

        // ⑫ 分批滚动：先有副本（2→4→6），再切流量（10%→50%→100%），最后改版本指针
        boolean started = svc.deploy(new InferenceService.Spec("aiplat/detector:1.1.0", "1.1.0", 6));
        List<String> surgeKinds = new ArrayList<>();
        List<Integer> readyStages = new ArrayList<>();
        for (int i = 0; i < 3; i++) {
            surgeKinds.add(svc.reconcile().kind());
            readyStages.add(svc.status().readyNew());
        }
        List<Integer> trafficStages = new ArrayList<>();
        for (int i = 0; i < 3; i++) {
            svc.reconcile();
            trafficStages.add(svc.status().newTrafficPct());
        }
        InferenceService.Action idle = svc.reconcile();
        InferenceService.Status converged = svc.status();
        check(pass, started && surgeKinds.equals(List.of("SURGE", "SURGE", "SURGE"))
                        && readyStages.equals(List.of(2, 4, 6)) && trafficStages.equals(List.of(10, 50, 100))
                        && converged.phase() == InferenceService.Phase.CONVERGED
                        && converged.currentVersion().equals("1.1.0") && converged.ready() == 6
                        && converged.readyNew() == 0 && idle.kind().equals("NONE"),
                "滚动发布：6 副本按批 2 推进 " + readyStages + "，副本齐备后流量 " + trafficStages
                        + "，收敛到 1.1.0（已收敛时循环空转，不再产生动作）");

        // ⑬ 灰度 50% 时健康失败 → 回滚：流量归零、副本排空、版本指针回到旧版本
        svc.deploy(new InferenceService.Spec("aiplat/detector:1.2.0", "1.2.0", 6));
        for (int i = 0; i < 5; i++) {
            svc.reconcile();       // 3 批副本 + 流量 10% + 流量 50%
        }
        InferenceService.Status beforeRollback = svc.status();
        svc.reportUnhealthy("灰度观察期指标劣化：p99 延迟 320ms > 阈值 200ms");
        int guard = 0;
        while (!svc.reconcile().kind().equals("NONE") && ++guard < 20) {
            // 回滚同样走控制器循环：流量归零 → 排空候选副本 → 回到旧版本
        }
        InferenceService.Status rolledBack = svc.status();
        check(pass, beforeRollback.newTrafficPct() == 50 && beforeRollback.readyNew() == 6
                        && rolledBack.phase() == InferenceService.Phase.ROLLED_BACK
                        && rolledBack.currentVersion().equals("1.1.0") && rolledBack.readyOld() == 6
                        && rolledBack.readyNew() == 0 && rolledBack.newTrafficPct() == 0
                        && rolledBack.unhealthyReason() != null,
                "灰度回滚：1.2.0 灰度 50% 时健康检查失败 → 流量归零、候选副本排空，回到 1.1.0 全量 6 副本（回滚即反向收敛）");

        // ================= G. 运维一屏与指标（3.8） =================

        // 留一个运行中任务 + 一个排队任务，让一屏的四块都有非平凡读数
        plat.submit(new JobSpec("cv", "reranker", 4, 7, 120, T0 + 500_000));
        plat.submit(new JobSpec("cv", "llm-sft", 6, 8, 600, T0 + 501_000));
        List<String> lastRound = plat.schedule();      // 6 卡先拿卡，4 卡任务因放不下继续排队

        OpsConsole ops = plat.ops("detector-svc");
        ops.print();
        OpsConsole.OpsView view = ops.snapshot();
        String metrics = ops.prometheusText();
        check(pass, lastRound.size() == 1 && view.gpusTotal() == 8 && view.gpusAllocated() == 6
                        && view.gpusFree() == 2 && view.utilizationPct() == 75.0
                        && view.jobsQueued() == 1 && view.jobsRunning() == 1
                        && view.jobsSucceeded() == 2 && view.jobsFailed() == 1
                        && view.prodVersion().equals("detector:1.1.0")
                        && view.serviceReady() == 6 && view.serviceDesired() == 6
                        && view.serviceVersion().equals("1.1.0") && view.servicePhase().equals("ROLLED_BACK")
                        && view.gpuSecondsTotal() > 0
                        && metric(metrics, "aiplat_jobs_queued") == 1
                        && metric(metrics, "aiplat_gpus_allocated") == 6
                        && metric(metrics, "aiplat_gpus_free") == 2
                        && metric(metrics, "aiplat_model_versions{stage=\"PROD\"}") == 1
                        && metric(metrics, "aiplat_service_replicas_ready{service=\"detector-svc\"}") == 6
                        && metric(metrics, "aiplat_service_traffic{service=\"detector-svc\",version=\"1.1.0\"}") == 100,
                "运维一屏：队列(1 排队/1 运行/2 成功/1 失败)、算力(6/8 已分配, 空闲 2, 计量 "
                        + view.gpuSecondsTotal() + " GPU·秒)、版本(PROD detector:1.1.0)、服务(就绪 6/6)四块齐全，"
                        + "Prometheus 文本与快照逐项一致");

        // ---- 验收汇总：14 项全绿才算通过，有 FAIL 直接非零退出，便于 CI 判定 ----
        System.out.printf("ALL PASS: %d/14%n", pass.get());
        if (pass.get() != 14) {
            System.exit(1);
        }
    }

    /** 从 Prometheus 文本中取样本值：匹配 `样本名{标签} 值` 这样的整行，找不到返回 -1。 */
    private static double metric(String text, String sample) {
        for (String line : text.split("\n")) {
            if (line.startsWith(sample + " ")) {
                return Double.parseDouble(line.substring(sample.length() + 1).trim());
            }
        }
        return -1.0;
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
