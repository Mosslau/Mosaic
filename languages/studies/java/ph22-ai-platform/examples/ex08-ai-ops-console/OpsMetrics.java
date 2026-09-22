// languages/java/ph22-ai-platform/examples/ex08-ai-ops-console/OpsMetrics.java —— 运维一屏的不可变数据快照：队列 / 算力 / 版本分布 / 服务就绪
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex08 *.java && java -cp /tmp/ph22-ex08 AiOpsDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 值班看板只需要回答四个问题：队列堵不堵、卡用没用满、模型是哪个版本、服务健康不健康。
 * 本 record 就是这四个答案的**不可变**快照：构造时对三个 Map 做防御性拷贝，
 * 于是渲染期间底层状态源怎么变都不会让一屏出现「一半新一半旧」的脏读（3.8）。
 */
public record OpsMetrics(
        int jobsQueued,
        int gpusAllocated,
        int gpusFree,
        Map<String, Integer> jobsByState,
        Map<String, Integer> modelVersionsByStage,
        Map<String, Integer> serviceReplicasReady) {

    /** 任务状态的规范顺序：固定顺序渲染 → 输出可 diff，也能直接贴进值班记录。 */
    public static final List<String> STATES = List.of("QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED");

    /** 模型阶段的规范顺序。 */
    public static final List<String> STAGES = List.of("STAGING", "PROD", "ARCHIVED");

    public OpsMetrics {
        if (jobsQueued < 0 || gpusAllocated < 0 || gpusFree < 0) {
            throw new IllegalArgumentException("运维快照不能出现负数：" + jobsQueued + "/" + gpusAllocated + "/" + gpusFree);
        }
        jobsByState = Map.copyOf(jobsByState);
        modelVersionsByStage = Map.copyOf(modelVersionsByStage);
        serviceReplicasReady = Map.copyOf(serviceReplicasReady);
    }

    public int gpusTotal() {
        return gpusAllocated + gpusFree;
    }

    /** 利用率 = 已分配 / 总量；总量为 0 时定义为 0——面板宁可是 0，也不能出现除零变成 NaN。 */
    public double gpuUtilizationPct() {
        int total = gpusTotal();
        return total == 0 ? 0.0 : gpusAllocated * 100.0 / total;
    }

    /** 空状态快照：集群刚起、还没有任何任务/模型/服务时也能渲染出合法的 0 值面板。 */
    public static OpsMetrics empty() {
        return new OpsMetrics(0, 0, 0, zeroed(STATES), zeroed(STAGES), Map.of());
    }

    /** 规范枚举全部预置为 0：保证「空」快照与真实空集群的快照逐字段相等。 */
    private static Map<String, Integer> zeroed(List<String> keys) {
        Map<String, Integer> map = new LinkedHashMap<>();
        for (String key : keys) {
            map.put(key, 0);
        }
        return map;
    }
}
