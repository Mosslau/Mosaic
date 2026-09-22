// languages/java/ph22-ai-platform/examples/ex06-data-versioning/DataVersionDemo.java —— 数据集/特征版本台账演练：校验和冲突、快照一致、training-serving skew 防护
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex06 *.java && java -cp /tmp/ph22-ex06 DataVersionDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：8/8 PASS）
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class DataVersionDemo {

    public static void main(String[] args) {
        AtomicInteger pass = new AtomicInteger();
        int total = 8;

        // ---------- 数据（确定性自造）：orders 数据集的三个版本 + 一个特征集 ----------
        DataVersionRegistry registry = new DataVersionRegistry();
        DatasetVersion ordersV1 = new DatasetVersion("orders", "v1", "sha256:aa11", 120_000, "job-1001");
        DatasetVersion ordersV2 = new DatasetVersion("orders", "v2", "sha256:bb22", 135_000, "job-1002");
        DatasetVersion ordersV3 = new DatasetVersion("orders", "v3", "sha256:cc33", 150_000, "job-1003");

        // 1) 登记成功 + 可按 (name, version) 查询 + 历史可追溯
        DatasetVersion registered = registry.registerDataset(ordersV1);
        registry.registerDataset(ordersV2);
        registry.registerDataset(ordersV3);
        boolean queryable = registry.dataset("orders", "v2").map(ordersV2::equals).orElse(false)
                && registry.dataset("orders", "v9").isEmpty()
                && registry.history("orders").equals(List.of(ordersV1, ordersV2, ordersV3));
        check(pass, registered.equals(ordersV1) && queryable,
                "数据集版本登记成功：可按 (name, version) 查询，历史按登记顺序返回 [v1, v2, v3]");

        // 2) 重复登记同一 (版本, 校验和) 幂等：返回台账原条目，历史不重复追加
        DatasetVersion again = registry.registerDataset(new DatasetVersion("orders", "v1", "sha256:aa11", 120_000, "job-1001"));
        check(pass, again.equals(ordersV1) && registry.history("orders").size() == 3,
                "重复登记同一 (版本, 校验和) 幂等：返回台账原条目，历史仍为 3 条");

        // 3) 同一版本号登记不同校验和 → 拒绝（原因里两个校验和都要出现，才能直接定位）
        String conflict = failure(() ->
                registry.registerDataset(new DatasetVersion("orders", "v1", "sha256:dead", 120_000, "job-9999")));
        check(pass, conflict != null && conflict.contains("sha256:aa11") && conflict.contains("sha256:dead"),
                "同一版本号登记不同校验和被拒（原因含双方校验和）：" + conflict);

        // 4) 快照一致 → 通过
        check(pass, failure(() -> registry.assertSnapshot(ordersV2, "sha256:bb22")) == null,
                "快照一致通过：任务实读 checksum == 台账登记 checksum（orders v2）");

        // 5) 快照不一致 → 拦下（数据被就地覆盖的典型信号）
        String snapshotMismatch = failure(() -> registry.assertSnapshot(ordersV2, "sha256:zz99"));
        check(pass, snapshotMismatch != null && snapshotMismatch.contains("快照不一致")
                        && snapshotMismatch.contains("sha256:zz99"),
                "快照不一致被拦：实读 checksum 与登记版本不符 → " + snapshotMismatch);

        // 6) 训练/推理特征版本不一致 → 拦下（training-serving skew 的第一道闸）
        FeatureVersion train = new FeatureVersion("user-embedding", "v3", "sha256:tr3");
        FeatureVersion serveOld = new FeatureVersion("user-embedding", "v2", "sha256:tr3");
        registry.registerFeature(train);
        String versionSkew = failure(() -> registry.assertTrainServeConsistent(train, serveOld));
        check(pass, versionSkew != null && versionSkew.contains("training-serving skew")
                        && versionSkew.contains("v3") && versionSkew.contains("v2"),
                "训练/推理特征版本不一致被拦（training-serving skew）：" + versionSkew);

        // 7) 版本号相同但 transformHash 不同 → 同样拦下；三项全等才放行
        FeatureVersion serveHashDrift = new FeatureVersion("user-embedding", "v3", "sha256:tr9");
        String hashSkew = failure(() -> registry.assertTrainServeConsistent(train, serveHashDrift));
        boolean consistentPasses = failure(() ->
                registry.assertTrainServeConsistent(train, new FeatureVersion("user-embedding", "v3", "sha256:tr3"))) == null;
        boolean featureQuery = registry.feature("user-embedding").map(train::equals).orElse(false);
        check(pass, hashSkew != null && hashSkew.contains("transformHash") && consistentPasses && featureQuery,
                "版本号相同但 transformHash 不同也被拦（三项全等才放行）：" + hashSkew);

        // 8) 版本单调递增：登记 v0 → 拒绝，历史与已登记版本不变
        String downgrade = failure(() ->
                registry.registerDataset(new DatasetVersion("orders", "v0", "sha256:ff00", 100_000, "job-0000")));
        check(pass, downgrade != null && downgrade.contains("单调递增")
                        && registry.history("orders").equals(List.of(ordersV1, ordersV2, ordersV3)),
                "版本台账单调递增：登记 v0 被拒，历史仍为 [v1, v2, v3]");

        System.out.printf("ALL PASS: %d/%d%n", pass.get(), total);
        if (pass.get() != total) {
            System.exit(1);
        }
    }

    /** 期望「必须抛异常」的断言：返回可读原因，未抛异常则返回 null。 */
    private static String failure(Runnable action) {
        try {
            action.run();
            return null;
        } catch (IllegalStateException | IllegalArgumentException e) {
            return e.getMessage();
        }
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
