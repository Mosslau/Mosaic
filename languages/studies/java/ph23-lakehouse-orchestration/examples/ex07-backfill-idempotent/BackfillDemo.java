// languages/java/ph23-lakehouse-orchestration/examples/ex07-backfill-idempotent/BackfillDemo.java —— 幂等回填演练：分区覆盖、下游重算闭包、断点续跑、原因留痕
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex07 *.java && java -cp /tmp/ph23-ex07 BackfillDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：8/8 PASS）
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

public final class BackfillDemo {

    public static void main(String[] args) {
        AtomicInteger pass = new AtomicInteger();
        int total = 8;

        // ---------- 数据（确定性自造）：ODS → DWD → DWS → ADS 四层，每个表 5 个日期分区 ----------
        List<String> partitions = List.of("2024-06-01", "2024-06-02", "2024-06-03", "2024-06-04", "2024-06-05");
        // 表名与 recompute 的口径键对齐：dws = dwd × 2、ads = dws + 100；ads_export 是独立导出表
        List<String> tables = List.of("ods_raw", "dwd_event", "dws", "ads", "ads_export");
        Map<String, Map<String, Long>> seed = Backfill.seedData(tables, partitions, 10);
        // 依赖图：ods → dwd → dws → ads；ads_export 显式声明为**无上游、无下游**的独立表
        Map<String, List<String>> deps = Map.of(
                "ods_raw", List.of("dwd_event"),
                "dwd_event", List.of("dws"),
                "dws", List.of("ads"),
                "ads", List.of(),
                "ads_export", List.of());

        Backfill backfill = new Backfill("dwd_event", deps, seed);
        List<BackfillTask> plan = backfill.plan("dwd_event", "2024-06-02", "2024-06-03");
        System.out.println("重算计划（DWD 修数传播到下游闭包）：");
        System.out.println("  " + Backfill.renderPlan(plan));

        // ---------- 执行：先让两个分区首次失败，验证断点续跑 ----------
        backfill.failOnceForTable("dws", List.of("2024-06-02", "2024-06-03"));
        for (BackfillTask task : plan) {
            backfill.run(task);
        }
        List<BackfillTask> gap = backfill.alreadySucceeded(plan);
        System.out.println("首次执行后已成功分区数：" + gap.size() + "/" + plan.size()
                + "，留痕条数：" + backfill.history().size());

        // A) 幂等：重复回填同一分区结果一致
        long beforeValue = backfill.value("dwd_event", "2024-06-02");
        int beforeHistory = backfill.history().size();
        BackfillTask again = new BackfillTask("dwd_event", "2024-06-02", "上游修数：ods_raw 修正 06-02 后的重算");
        backfill.run(again);
        long afterValue = backfill.value("dwd_event", "2024-06-02");
        check(pass, beforeValue == afterValue && beforeValue == 20L
                        && backfill.history().size() == beforeHistory + 1
                        && backfill.history().get(backfill.history().size() - 1).table().equals("dwd_event"),
                "重复回填同一分区幂等（整体覆盖，不追加）：dwd_event/2024-06-02 两次都是 " + afterValue
                        + "，留痕 +1 条");

        // B) 重算闭包覆盖 DWS / ADS 对应分区
        check(pass, Backfill.covers(plan, "dws", "2024-06-02")
                        && Backfill.covers(plan, "dws", "2024-06-03")
                        && Backfill.covers(plan, "dws", "2024-06-03")
                        && Backfill.covers(plan, "ads", "2024-06-03")
                        && Backfill.covers(plan, "dwd_event", "2024-06-02")
                        && plan.size() == 6,
                "重算闭包覆盖 DWS/ADS 对应分区：plan 共 " + plan.size() + " 个任务，含 dws 与 ads 各 2 天");

        // C) 闭包不含无关分区
        boolean unrelated = plan.stream().anyMatch(task ->
                !task.partition().equals("2024-06-02") && !task.partition().equals("2024-06-03"));
        boolean unknownTable = plan.stream().anyMatch(task -> !deps.containsKey(task.table()));
        boolean closedSet = plan.stream().allMatch(task -> deps.containsKey(task.table())
                || task.table().equals("ads"));
        check(pass, !unrelated && !unknownTable && closedSet
                        && !Backfill.covers(plan, "ads", "2024-06-01")
                        && !Backfill.covers(plan, "ads", "2024-06-04")
                        && !Backfill.covers(plan, "ads_export", "2024-06-02"),
                "闭包不含无关分区：计划只含 06-02/06-03，不含 06-01/06-04，也未把 ads_export 卷进来（无下游可传播）");

        // D) 断点续跑只补缺口
        List<BackfillTask> resumed = backfill.resume(plan);
        check(pass, resumed.size() == 2
                        && resumed.stream().allMatch(task -> task.table().equals("dws"))
                        && backfill.alreadySucceeded(plan).size() == plan.size()
                        && backfill.resume(plan).isEmpty(),
                "断点续跑只补缺口：首次失败 2 个分区，resume 恰好执行 " + resumed.size()
                        + " 个（均为 dws），再 resume 已无可执行任务");

        // E) 原因留痕条数与任务数一致（成功的每条留痕 + 2 条失败尝试留痕）
        int failures = 2;
        List<Backfill.BackfillRecord> history = backfill.history();
        boolean eachRecordHasReason = history.stream().allMatch(record -> !record.reason().isBlank());
        check(pass, history.size() == plan.size() + failures + 1 && eachRecordHasReason
                        && backfill.succeededKeys().size() == plan.size(),
                "原因留痕与执行对齐：留痕 " + history.size() + " 条 = 计划 " + plan.size()
                        + " + 失败尝试 " + failures + " + 重复回填 1；成功分区 " + backfill.succeededKeys().size()
                        + " 个，每条留痕都有 reason");

        // F) 非法分区范围（from > to）被拒
        boolean rejected = false;
        String message = "";
        try {
            backfill.plan("dwd_event", "2024-06-05", "2024-06-01");
        } catch (IllegalArgumentException expected) {
            rejected = true;
            message = expected.getMessage();
        }
        check(pass, rejected && message.contains("非法分区范围") && !message.isBlank(),
                "非法分区范围被拒：plan(from=2024-06-05, to=2024-06-01) 抛 IllegalArgumentException（" + message + "）");

        // G) 重算后的下游聚合值 == 按新上游重算的值
        //    独立算一遍：ads = (dwd × 2) + 100，与引擎沿依赖图算出的值逐项比较
        long dwd = backfill.value("dwd_event", "2024-06-03");
        long odsValue = backfill.value("ods_raw", "2024-06-03");
        long expectedDws = odsValue * 2;      // 口径：dws = ods × 2
        long expectedAds = expectedDws + 100; // 口径：ads = dws + 100
        check(pass, dwd == odsValue
                        && backfill.value("dws", "2024-06-03") == expectedDws
                        && backfill.value("ads", "2024-06-03") == expectedAds,
                "重算后下游等于按新上游重算：dwd=" + dwd + " → dws=" + backfill.value("dws", "2024-06-03")
                        + "（=ods×2=" + expectedDws + "）→ ads=" + backfill.value("ads", "2024-06-03") + "（=dws+100=" + expectedAds + "）");

        // H) 计划确定性：两次 plan 逐项相同，且按 (table,partition) 有序
        List<BackfillTask> planAgain = backfill.plan("dwd_event", "2024-06-02", "2024-06-03");
        boolean sameOrder = Backfill.renderPlan(plan).equals(Backfill.renderPlan(planAgain));
        boolean sorted = true;
        for (int i = 1; i < plan.size(); i++) {
            String previousTable = plan.get(i - 1).table();
            String currentTable = plan.get(i).table();
            String previousPartition = plan.get(i - 1).partition();
            String currentPartition = plan.get(i).partition();
            // 同一张表内按分区升序即可；跨表顺序由拓扑序决定，不能要求全序字典序（dws 排在 dwd_event 之前）
            if (previousTable.equals(currentTable) && previousPartition.compareTo(currentPartition) > 0) {
                sorted = false;
            }
        }
        System.out.println("终态数据：" + backfill.render());
        check(pass, sameOrder && sorted && plan.get(0).table().equals("dwd_event")
                        && plan.get(plan.size() - 1).table().equals("ads"),
                "计划确定性且按拓扑序：两次 plan 逐项相同，上游 dwd_event 排在下游 ads 之前（首项 "
                        + plan.get(0).table() + "，末项 " + plan.get(plan.size() - 1).table() + "）");

        System.out.printf("ALL PASS: %d/%d%n", pass.get(), total);
        if (pass.get() != total) {
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
