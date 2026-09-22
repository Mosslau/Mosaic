// languages/java/ph22-ai-platform/examples/ex08-ai-ops-console/OpsDashboard.java —— 多状态源聚合 → 运维一屏文本 + Prometheus 文本指标
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex08 *.java && java -cp /tmp/ph22-ex08 AiOpsDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * 运维一屏的数据来自四个**不同**的状态源，而不是某一张表：
 *   任务列表（控制面的聚合根）→ 队列深度与状态分布；
 *   算力池（GPU 台账）→ 已分配 / 空闲与利用率；
 *   模型注册表 → 版本按阶段分布；
 *   推理服务列表 → 就绪副本数。
 * 本类只做「聚合 + 渲染」两件事，且输出顺序全部确定（规范枚举在前、其余按字典序），
 * 因为值班文本是要被 diff 的：顺序抖动会让人以为是状态变了（与 ph21 3.8 同法）。
 * Prometheus 文本遵循 `# HELP` / `# TYPE` / `name{label="v"} value` 语法。
 */
public final class OpsDashboard {

    /** 状态源 1：训练任务（只取渲染需要的两个字段）。 */
    public record Job(String id, String state) { }

    /** 状态源 2：算力池（GPU 总量 + 每任务占用）。 */
    public record GpuPool(int total, Map<String, Integer> allocatedByJob) {
        public GpuPool {
            if (total < 0) {
                throw new IllegalArgumentException("GPU 总量不能为负：" + total);
            }
            allocatedByJob = Map.copyOf(allocatedByJob);
        }
    }

    /** 状态源 3：模型注册表条目（哪个模型的哪个版本处在哪个阶段）。 */
    public record ModelVersionEntry(String model, String version, String stage) { }

    /** 状态源 4：推理服务（就绪副本数）。 */
    public record ServiceStatus(String service, int replicasReady) { }

    private final List<Job> jobs;
    private final GpuPool pool;
    private final List<ModelVersionEntry> versions;
    private final List<ServiceStatus> services;

    public OpsDashboard(List<Job> jobs, GpuPool pool, List<ModelVersionEntry> versions, List<ServiceStatus> services) {
        this.jobs = List.copyOf(jobs);
        this.pool = pool;
        this.versions = List.copyOf(versions);
        this.services = List.copyOf(services);
    }

    /** 四个状态源 → 一张不可变快照。 */
    public OpsMetrics snapshot() {
        Map<String, Integer> byState = zeroed(OpsMetrics.STATES);
        int queued = 0;
        for (Job job : jobs) {
            byState.merge(job.state(), 1, Integer::sum);   // 未知状态也计数，不静默丢弃
            if ("QUEUED".equals(job.state())) {
                queued++;
            }
        }

        int allocated = pool.allocatedByJob().values().stream().mapToInt(Integer::intValue).sum();
        int free = Math.max(0, pool.total() - allocated);   // 台账超卖时不渲染出负数

        Map<String, Integer> byStage = zeroed(OpsMetrics.STAGES);
        for (ModelVersionEntry version : versions) {
            byStage.merge(version.stage(), 1, Integer::sum);
        }

        Map<String, Integer> ready = new TreeMap<>();   // 服务名排序 → 输出稳定
        for (ServiceStatus service : services) {
            ready.merge(service.service(), service.replicasReady(), Integer::sum);
        }

        return new OpsMetrics(queued, allocated, free, byState, byStage, ready);
    }

    /** ① 一屏文本：队列 / 算力利用率 / 版本分布 / 服务就绪四块。 */
    public static String renderScreen(OpsMetrics m) {
        StringBuilder sb = new StringBuilder();
        sb.append("+---------------------- AI 平台运维一屏 ----------------------+\n");
        sb.append(String.format(" [队列]     排队 %d 个 | %s%n",
                m.jobsQueued(), counters(m.jobsByState(), OpsMetrics.STATES)));
        sb.append(String.format(" [算力]     已分配 %d / 总 %d（利用率 %.1f%%）| 空闲 %d%n",
                m.gpusAllocated(), m.gpusTotal(), m.gpuUtilizationPct(), m.gpusFree()));
        sb.append(String.format(" [模型版本] %s%n", counters(m.modelVersionsByStage(), OpsMetrics.STAGES)));
        sb.append(String.format(" [服务就绪] %s%n", counters(m.serviceReplicasReady(), sortedKeys(m.serviceReplicasReady()))));
        sb.append("+-------------------------------------------------------------+\n");
        return sb.toString();
    }

    /** ② Prometheus 文本指标：平台自己该暴露的六个指标族。 */
    public static String renderPrometheus(OpsMetrics m) {
        StringBuilder sb = new StringBuilder();
        plain(sb, "aiplat_jobs_queued", "排队中的训练任务数", "gauge", m.jobsQueued());
        plain(sb, "aiplat_gpus_allocated", "已分配 GPU 卡数", "gauge", m.gpusAllocated());
        plain(sb, "aiplat_gpus_free", "空闲 GPU 卡数", "gauge", m.gpusFree());
        labelled(sb, "aiplat_jobs_total", "训练任务按状态计数", "counter", "state",
                orderWithExtras(m.jobsByState(), OpsMetrics.STATES), m.jobsByState());
        labelled(sb, "aiplat_model_versions", "模型版本按阶段分布", "gauge", "stage",
                orderWithExtras(m.modelVersionsByStage(), OpsMetrics.STAGES), m.modelVersionsByStage());
        labelled(sb, "aiplat_service_replicas_ready", "推理服务就绪副本数", "gauge", "service",
                sortedKeys(m.serviceReplicasReady()), m.serviceReplicasReady());
        return sb.toString();
    }

    private static void plain(StringBuilder sb, String name, String help, String type, long value) {
        sb.append("# HELP ").append(name).append(' ').append(help).append('\n');
        sb.append("# TYPE ").append(name).append(' ').append(type).append('\n');
        sb.append(name).append(' ').append(value).append('\n');
    }

    private static void labelled(StringBuilder sb, String name, String help, String type, String label,
                                 List<String> keys, Map<String, Integer> values) {
        sb.append("# HELP ").append(name).append(' ').append(help).append('\n');
        sb.append("# TYPE ").append(name).append(' ').append(type).append('\n');
        for (String key : keys) {
            sb.append(name).append('{').append(label).append("=\"").append(key).append("\"} ")
                    .append(values.getOrDefault(key, 0)).append('\n');
        }
    }

    private static Map<String, Integer> zeroed(List<String> keys) {
        Map<String, Integer> map = new LinkedHashMap<>();
        for (String key : keys) {
            map.put(key, 0);
        }
        return map;
    }

    private static String counters(Map<String, Integer> values, List<String> order) {
        StringBuilder sb = new StringBuilder();
        for (String key : orderWithExtras(values, order)) {
            if (sb.length() > 0) {
                sb.append(' ');
            }
            sb.append(key).append('=').append(values.getOrDefault(key, 0));
        }
        return sb.toString();
    }

    /** 规范枚举在前（固定顺序），出现规范之外的新键时按字典序追加在后——既稳定又不丢数据。 */
    private static List<String> orderWithExtras(Map<String, Integer> values, List<String> canonical) {
        List<String> keys = new ArrayList<>(canonical);
        values.keySet().stream().filter(key -> !canonical.contains(key)).sorted().forEach(keys::add);
        return keys;
    }

    private static List<String> sortedKeys(Map<String, Integer> values) {
        return new ArrayList<>(new TreeMap<>(values).keySet());
    }
}
