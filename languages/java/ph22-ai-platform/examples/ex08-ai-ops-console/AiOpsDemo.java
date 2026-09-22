// languages/java/ph22-ai-platform/examples/ex08-ai-ops-console/AiOpsDemo.java —— 运维一屏与 Prometheus 文本指标的渲染自检
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex08 *.java && java -cp /tmp/ph22-ex08 AiOpsDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Pattern;

public final class AiOpsDemo {

    /** Prometheus 文本样本行语法：可选的一组 label="value"，末尾是数值。 */
    private static final Pattern SAMPLE = Pattern.compile(
            "^[a-zA-Z_:][a-zA-Z0-9_:]*(\\{[a-zA-Z_][a-zA-Z0-9_]*=\"[^\"]*\""
                    + "(,[a-zA-Z_][a-zA-Z0-9_]*=\"[^\"]*\")*\\})? -?[0-9]+(\\.[0-9]+)?$");

    private static final List<String> FAMILIES = List.of(
            "aiplat_jobs_queued", "aiplat_gpus_allocated", "aiplat_gpus_free",
            "aiplat_jobs_total", "aiplat_model_versions", "aiplat_service_replicas_ready");

    public static void main(String[] args) {
        AtomicInteger pass = new AtomicInteger();
        int total = 7;

        // ---------- 数据（确定性自造）：任务列表 / 算力池 / 模型注册表 / 服务列表四个状态源 ----------
        List<OpsDashboard.Job> jobs = List.of(
                new OpsDashboard.Job("job-201", "RUNNING"),
                new OpsDashboard.Job("job-202", "RUNNING"),
                new OpsDashboard.Job("job-203", "QUEUED"),
                new OpsDashboard.Job("job-204", "QUEUED"),
                new OpsDashboard.Job("job-205", "SUCCEEDED"),
                new OpsDashboard.Job("job-206", "FAILED"));
        OpsDashboard.GpuPool pool = new OpsDashboard.GpuPool(8, Map.of("job-201", 4, "job-202", 2));
        List<OpsDashboard.ModelVersionEntry> versions = List.of(
                new OpsDashboard.ModelVersionEntry("ranker", "v1", "PROD"),
                new OpsDashboard.ModelVersionEntry("ranker", "v2", "STAGING"),
                new OpsDashboard.ModelVersionEntry("embed", "v3", "PROD"),
                new OpsDashboard.ModelVersionEntry("embed", "v2", "ARCHIVED"));
        List<OpsDashboard.ServiceStatus> services = List.of(
                new OpsDashboard.ServiceStatus("ranker", 3),
                new OpsDashboard.ServiceStatus("embed", 2),
                new OpsDashboard.ServiceStatus("feature-store", 0));

        OpsDashboard dashboard = new OpsDashboard(jobs, pool, versions, services);
        OpsMetrics metrics = dashboard.snapshot();
        String screen = OpsDashboard.renderScreen(metrics);
        String prometheus = OpsDashboard.renderPrometheus(metrics);

        System.out.print(screen);
        System.out.print(prometheus);

        List<String> lines = prometheus.lines().filter(line -> !line.isBlank()).toList();
        List<String> samples = lines.stream().filter(line -> !line.startsWith("#")).toList();

        // 1) 一屏四块齐全
        check(pass, screen.contains("[队列]") && screen.contains("[算力]")
                        && screen.contains("[模型版本]") && screen.contains("[服务就绪]"),
                "一屏包含四块：队列 / 算力利用率 / 模型版本分布 / 服务就绪");

        // 2) 样本行数与指标数一致：3 个无标签指标 + 5 个状态 + 3 个阶段 + 3 个服务 = 14
        int expectedSamples = 3 + OpsMetrics.STATES.size() + OpsMetrics.STAGES.size() + services.size();
        boolean noDuplicateSeries = samples.stream().distinct().count() == samples.size();
        check(pass, samples.size() == expectedSamples && noDuplicateSeries,
                "Prometheus 样本行数与指标数一致：3 无标签 + 5 状态 + 3 阶段 + 3 服务 = " + samples.size() + " 行，无重复序列");

        // 3) 每个指标族都有且仅有一组 # HELP / # TYPE，且声明在样本行之前
        boolean declared = FAMILIES.stream().allMatch(family -> familyDeclared(lines, family));
        check(pass, declared,
                "Prometheus 语法自检：6 个指标族各有且仅有 1 组 # HELP / # TYPE，且都在样本行之前");

        // 4) 样本行语法合法 + {state=...} 标签值带引号且是合法状态枚举
        boolean syntaxOk = samples.stream().allMatch(line -> SAMPLE.matcher(line).matches());
        List<String> stateLabels = samples.stream()
                .filter(line -> line.startsWith("aiplat_jobs_total{"))
                .map(line -> line.substring(line.indexOf("state=\"") + 7, line.indexOf("\"}")))
                .toList();
        boolean stateLabelsOk = stateLabels.size() == OpsMetrics.STATES.size()
                && stateLabels.stream().allMatch(OpsMetrics.STATES::contains);
        check(pass, syntaxOk && stateLabelsOk,
                "标签值合法：全部样本行匹配 Prometheus 语法，aiplat_jobs_total 的 state 标签全部双引号包裹且属于 "
                        + OpsMetrics.STATES);

        // 5) 利用率 = allocated / total，池口径一致
        check(pass, metrics.gpusAllocated() == 6 && metrics.gpusFree() == 2 && metrics.gpusTotal() == 8
                        && Math.abs(metrics.gpuUtilizationPct() - 75.0) < 1e-9,
                "利用率计算正确：已分配 6 / 总 8 = " + metrics.gpuUtilizationPct() + "%，空闲 " + metrics.gpusFree());

        // 6) 服务就绪副本数与输入一致，且队列深度口径正确
        boolean readyMatches = metrics.serviceReplicasReady()
                .equals(Map.of("ranker", 3, "embed", 2, "feature-store", 0));
        check(pass, readyMatches && metrics.jobsQueued() == 2 && metrics.jobsByState().get("QUEUED") == 2,
                "就绪副本数与输入一致：" + metrics.serviceReplicasReady() + "，队列深度 " + metrics.jobsQueued() + " 个");

        // 7) 空状态不崩且输出 0 值
        OpsMetrics empty = new OpsDashboard(List.of(), new OpsDashboard.GpuPool(0, Map.of()), List.of(), List.of())
                .snapshot();
        String emptyScreen = OpsDashboard.renderScreen(empty);
        String emptyProm = OpsDashboard.renderPrometheus(empty);
        check(pass, empty.equals(OpsMetrics.empty()) && empty.gpuUtilizationPct() == 0.0
                        && !emptyScreen.contains("NaN")
                        && emptyProm.contains("aiplat_jobs_queued 0")
                        && emptyProm.contains("aiplat_gpus_allocated 0")
                        && emptyProm.contains("aiplat_gpus_free 0")
                        && emptyProm.contains("aiplat_jobs_total{state=\"QUEUED\"} 0"),
                "空状态不崩且输出 0 值：队列/分配/空闲均为 0，利用率为 0%（不出现 NaN）");

        System.out.printf("ALL PASS: %d/%d%n", pass.get(), total);
        if (pass.get() != total) {
            System.exit(1);
        }
    }

    /** 指标族是否「先声明、后出样本」：恰好一组 HELP/TYPE，且都排在首个样本行之前。 */
    private static boolean familyDeclared(List<String> lines, String name) {
        int help = indexOfPrefix(lines, "# HELP " + name + " ");
        int type = indexOfPrefix(lines, "# TYPE " + name + " ");
        int firstSample = -1;
        for (int i = 0; i < lines.size(); i++) {
            if (lines.get(i).startsWith(name + " ") || lines.get(i).startsWith(name + "{")) {
                firstSample = i;
                break;
            }
        }
        return help >= 0 && type >= 0 && firstSample > help && firstSample > type
                && countPrefix(lines, "# HELP " + name + " ") == 1
                && countPrefix(lines, "# TYPE " + name + " ") == 1;
    }

    private static int indexOfPrefix(List<String> lines, String prefix) {
        for (int i = 0; i < lines.size(); i++) {
            if (lines.get(i).startsWith(prefix)) {
                return i;
            }
        }
        return -1;
    }

    private static int countPrefix(List<String> lines, String prefix) {
        return (int) lines.stream().filter(line -> line.startsWith(prefix)).count();
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
