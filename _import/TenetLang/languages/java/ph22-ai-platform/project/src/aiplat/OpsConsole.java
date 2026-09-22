// project/src/aiplat/OpsConsole.java —— 运维一屏：队列/算力/版本/服务四块聚合 + Prometheus 文本
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

/**
 * 运维一屏（主文档 3.8）：AI 平台值班只需要回答四个问题——
 * <b>队列堵不堵、卡用没用满、模型是哪个版本、服务健康不健康</b>。
 *
 * <p>本类是各域的<b>只读聚合器</b>，不拥有任何数据（数据在池子/注册表/服务里）。
 * 因此同一份快照可以同时喂给「人看的一屏」与「机器抓的指标文本」，
 * 两者必然一致——「大屏和告警数字对不上」这类事故从结构上被排除。
 *
 * <p>Prometheus/Grafana 的部署与告警规则是 ph12/ph16 的内容，这里只示范平台该暴露哪些指标。
 */
public final class OpsConsole {

    private final AiPlatform platform;
    private final InferenceService service;

    public OpsConsole(AiPlatform platform, InferenceService service) {
        this.platform = platform;
        this.service = service;
    }

    /** 四块聚合快照：字段全部来自各域当前状态，无缓存、无副本。 */
    public OpsView snapshot() {
        GpuPool pool = platform.pool();
        int total = pool.total();
        int allocated = pool.allocatedGpus();
        int free = pool.free();
        double utilization = total == 0 ? 0.0 : allocated * 100.0 / total;

        ModelRegistry registry = platform.registry();
        InferenceService.Status st = service.status();

        return new OpsView(
                total, allocated, free, utilization,
                platform.queuedCount(), platform.runningCount(),
                platform.countByState("SUCCEEDED"), platform.countByState("FAILED"),
                registry.productionVersion(),
                registry.countStage(ModelVersion.Stage.PROD),
                registry.countStage(ModelVersion.Stage.STAGING),
                registry.countStage(ModelVersion.Stage.ARCHIVED),
                platform.meter().totalGpuSeconds(), platform.meter().eventCount(),
                service.name(), st.ready(), st.desired(), st.currentVersion(),
                st.phase().name(), service.currentTrafficPct());
    }

    /** 人看的一屏：四块 + 明细。 */
    public void print() {
        OpsView v = snapshot();
        System.out.println("+---------------------------- AI 平台运维一屏 ----------------------------+");
        System.out.printf("  [任务] 排队 %d | 运行中 %d | 成功 %d | 失败 %d%n",
                v.jobsQueued(), v.jobsRunning(), v.jobsSucceeded(), v.jobsFailed());
        System.out.printf("  [算力] GPU %d/%d 已分配（利用率 %.1f%%）| 空闲 %d | 累计计量 %d GPU·秒 / %d 条事件%n",
                v.gpusAllocated(), v.gpusTotal(), v.utilizationPct(), v.gpusFree(),
                v.gpuSecondsTotal(), v.meteringEvents());
        System.out.printf("  [版本] PROD=%s（PROD %d / STAGING %d / ARCHIVED %d）%n",
                v.prodVersion(), v.prodCount(), v.stagingCount(), v.archivedCount());
        System.out.printf("  [服务] %s 就绪 %d/%d | 当前版本 %s（流量 %d%%）| 阶段 %s%n",
                v.serviceName(), v.serviceReady(), v.serviceDesired(),
                v.serviceVersion(), v.serviceTrafficPct(), v.servicePhase());
        System.out.println("+------------------------------------------------------------------------+");
    }

    /**
     * Prometheus 文本指标（主文档 3.8 的五个指标）。
     *
     * <p>与 {@link #snapshot()} 共用同一份读数，所以「文本指标」与「一屏」不可能互相矛盾。
     */
    public String prometheusText() {
        OpsView v = snapshot();
        StringBuilder sb = new StringBuilder();
        sb.append("# 队列堵不堵 / 卡用没用满 / 模型是哪个版本 / 服务健康不健康\n");
        sb.append("aiplat_jobs_queued ").append(v.jobsQueued()).append('\n');
        sb.append("aiplat_jobs_running ").append(v.jobsRunning()).append('\n');
        sb.append("aiplat_jobs_total{state=\"succeeded\"} ").append(v.jobsSucceeded()).append('\n');
        sb.append("aiplat_jobs_total{state=\"failed\"} ").append(v.jobsFailed()).append('\n');
        sb.append("aiplat_gpus_total ").append(v.gpusTotal()).append('\n');
        sb.append("aiplat_gpus_allocated ").append(v.gpusAllocated()).append('\n');
        sb.append("aiplat_gpus_free ").append(v.gpusFree()).append('\n');
        sb.append("aiplat_gpus_utilization_pct ").append(v.utilizationPct()).append('\n');
        sb.append("aiplat_gpu_seconds_total ").append(v.gpuSecondsTotal()).append('\n');
        sb.append("aiplat_model_versions{stage=\"PROD\"} ").append(v.prodCount()).append('\n');
        sb.append("aiplat_model_versions{stage=\"STAGING\"} ").append(v.stagingCount()).append('\n');
        sb.append("aiplat_model_versions{stage=\"ARCHIVED\"} ").append(v.archivedCount()).append('\n');
        sb.append("aiplat_service_replicas_ready{service=\"").append(v.serviceName())
                .append("\"} ").append(v.serviceReady()).append('\n');
        sb.append("aiplat_service_replicas_desired{service=\"").append(v.serviceName())
                .append("\"} ").append(v.serviceDesired()).append('\n');
        sb.append("aiplat_service_traffic{service=\"").append(v.serviceName())
                .append("\",version=\"").append(v.serviceVersion()).append("\"} ")
                .append(v.serviceTrafficPct()).append('\n');
        return sb.toString();
    }

    /** 四块聚合读数（可直接被验收断言读取）。 */
    public record OpsView(int gpusTotal, int gpusAllocated, int gpusFree, double utilizationPct,
                          int jobsQueued, int jobsRunning, long jobsSucceeded, long jobsFailed,
                          String prodVersion, long prodCount, long stagingCount, long archivedCount,
                          long gpuSecondsTotal, int meteringEvents,
                          String serviceName, int serviceReady, int serviceDesired,
                          String serviceVersion, String servicePhase, int serviceTrafficPct) { }
}
