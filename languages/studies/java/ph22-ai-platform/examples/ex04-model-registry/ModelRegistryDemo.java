// languages/java/ph22-ai-platform/examples/ex04-model-registry/ModelRegistryDemo.java —— 模型注册表主入口：语义化比较、血缘校验、晋级门槛、唯一 PROD
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex04 *.java && java -cp /tmp/ph22-ex04 ModelRegistryDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：8/8 PASS）
//
// 场景：reranker 模型已有线上 PROD 2.9.0（指标 0.81），团队训练出 2.10.0（0.84）与 2.10.1（0.79）。
// 断言覆盖 3.4 的四条规则：语义化比较、血缘完整、禁止倒退、指标门槛，外加唯一 PROD 与有序查询。
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class ModelRegistryDemo {
    /** 断言总数：用于末尾 ALL PASS: N/N 与失败退出码。 */
    private static final int TOTAL_CHECKS = 8;

    public static void main(String[] args) {
        ModelRegistry registry = new ModelRegistry();
        String model = "reranker";

        // 台账起点：2.9.0 已是线上 PROD，2.8.0 是它的前身（已归档）
        ModelVersion v290 = registry.register(model, 2, 9, 0, "ds-2025-08", "job-100", 0.81);
        ModelVersion v280 = registry.register(model, 2, 8, 0, "ds-2025-07", "job-090", 0.78);
        registry.promote(model, 2, 9, 0);
        registry.archive(model, 2, 8, 0);

        // 新训练产出：2.10.0 指标更好，2.10.1 版本更高但指标退化
        ModelVersion v2100 = registry.register(model, 2, 10, 0, "ds-2025-09", "job-110", 0.84);
        ModelVersion v2101 = registry.register(model, 2, 10, 1, "ds-2025-09", "job-111", 0.79);

        AtomicInteger pass = new AtomicInteger();

        // 1) 语义化比较：2.10.0 > 2.9.0（字符串比较会得出相反结论，这是禁止倒退的地基）
        check(pass, v2100.compareTo(v290) > 0 && "reranker@2.10.0".equals(v2100.tag()),
                "语义化比较：2.10.0 > 2.9.0（逐段比数值，而非字符串），tag()=" + v2100.tag());

        // 2) 血缘缺失被拒：没有数据集版本或产出任务的版本不允许登记
        boolean lineageRejected = false;
        try {
            registry.register("reranker", 3, 0, 0, "  ", "job-200", 0.9);
        } catch (IllegalArgumentException e) {
            lineageRejected = true;
        }
        boolean lineageRejected2 = false;
        try {
            registry.register("reranker", 3, 0, 0, "ds-2025-10", "", 0.9);
        } catch (IllegalArgumentException e) {
            lineageRejected2 = true;
        }
        check(pass, lineageRejected && lineageRejected2,
                "血缘缺失被拒：datasetVersion 或 jobId 为空时 register 抛异常");

        // 3) 版本倒退被拒：2.8.0 比当前 PROD 2.9.0 旧，即使指标更高也不许把指针拨回去
        ModelVersion v300 = registry.register(model, 3, 0, 0, "ds-2025-10", "job-120", 0.99);
        boolean rollbackRejected = false;
        try {
            registry.promote(model, 2, 8, 0);
        } catch (IllegalStateException e) {
            rollbackRejected = true;
        }
        check(pass, rollbackRejected,
                "版本倒退被拒：2.8.0 低于当前 PROD 2.9.0，promote 抛 IllegalStateException");

        // 4) 指标不达标不得晋级：已登记的 2.10.1 版本更高，但 0.79 < 当前 PROD 0.81
        boolean metricRejected = false;
        try {
            registry.promote(model, 2, 10, 1);
        } catch (IllegalStateException e) {
            metricRejected = true;
        }
        check(pass, metricRejected,
                "指标不达标不得晋级：2.10.1 指标 0.79 劣于当前 PROD 0.81，promote 被拒");

        // 5) 晋级成功：2.10.0（指标 0.84 达标）接替线上
        ModelVersion promoted = registry.promote(model, 2, 10, 0);
        check(pass, promoted.stage() == ModelVersion.Stage.PROD
                        && registry.current(model).tag().equals("reranker@2.10.0"),
                "晋级成功：2.10.0 指标 0.84 ≥ 0.81，成为新的 PROD");

        // 6) 晋级后 PROD 唯一且旧的转 ARCHIVED：2.9.0 必须自动归档，台账不留两个线上版本
        List<ModelVersion> prodVersions = new ArrayList<>();
        for (ModelVersion v : registry.versions(model)) {
            if (v.stage() == ModelVersion.Stage.PROD) {
                prodVersions.add(v);
            }
        }
        boolean oldArchived = registry.versions(model).stream()
                .anyMatch(v -> v.major() == 2 && v.minor() == 9 && v.patch() == 0
                        && v.stage() == ModelVersion.Stage.ARCHIVED);
        check(pass, prodVersions.size() == 1 && oldArchived,
                "PROD 唯一：台账中只有 1 个 PROD（2.10.0），旧 PROD 2.9.0 转为 ARCHIVED");

        // 7) 按模型查询版本列表有序：2.8.0 → 2.9.0 → 2.10.0 → 2.10.1 → 3.0.0
        List<ModelVersion> ordered = registry.versions(model);
        boolean ascending = true;
        for (int i = 1; i < ordered.size(); i++) {
            if (ordered.get(i - 1).compareTo(ordered.get(i)) > 0) {
                ascending = false;
            }
        }
        check(pass, ascending && ordered.size() == 5
                        && ordered.get(2).tag().equals("reranker@2.10.0"),
                "版本列表升序：2.8.0 → 2.9.0 → 2.10.0 → 2.10.1 → 3.0.0（共 5 条）");

        // 8) 归档终态：已归档版本不能再被拉回线上，也不能重复归档
        boolean archivedTerminal = false;
        try {
            registry.promote(model, 2, 9, 0);
        } catch (IllegalStateException e) {
            archivedTerminal = true;
        }
        boolean doubleArchiveRejected = false;
        try {
            registry.archive(model, 2, 9, 0);
        } catch (IllegalStateException e) {
            doubleArchiveRejected = true;
        }
        check(pass, archivedTerminal && doubleArchiveRejected,
                "归档终态：ARCHIVED 版本不可晋级、不可重复归档");

        System.out.println("== reranker 版本台账（按语义化版本升序） ==");
        System.out.printf("  %-18s %-9s %-11s %-8s %s%n", "tag", "stage", "dataset", "jobId", "metric");
        for (ModelVersion v : registry.versions(model)) {
            System.out.printf("  %-18s %-9s %-11s %-8s %.3f%n",
                    v.tag(), v.stage(), v.datasetVersion(), v.jobId(), v.metric());
        }
        System.out.println("  当前 PROD: " + registry.current(model).tag());
        System.out.printf("ALL PASS: %d/%d%n", pass.get(), TOTAL_CHECKS);
        if (pass.get() != TOTAL_CHECKS) {
            System.exit(1);
        }
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
