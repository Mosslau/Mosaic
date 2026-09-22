// languages/java/ph23-lakehouse-orchestration/examples/ex04-compaction/CompactionDemo.java —— 小文件治理主入口：合并决策 + 读收益测算 + 幂等验证
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex04 *.java && java -cp /tmp/ph23-ex04 CompactionDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
//
// 场景：三个分区。2024-06-21 是流式写入留下的小文件灾区（10 × 1KB）需要合并；2024-06-01 文件数
// 没超阈值；2024-06-02 文件不多但每个都已达标——后两个都不该合并（合并是重写，要花算力和 IO）。
// 断言覆盖 3.4 / 4.2：非空方案、文件数下降、readSavedRatio > 0、字节口径、重复 apply 一致、空方案。
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class CompactionDemo {

    private static final int TOTAL = 7;

    public static void main(String[] args) {
        String smallPartition = "2024-06-21";
        long targetBytes = 8_192L;
        int minFiles = 3;

        // 灾区分区：10 个 1KB 小文件（共 10,000 字节 / 1,000 行）
        List<DataFile> smallFiles = new ArrayList<>();
        for (int i = 1; i <= 10; i++) {
            smallFiles.add(new DataFile(String.format("%s/part-%02d.parquet", smallPartition, i),
                    smallPartition, 100L, 1_000L));
        }
        // 文件数不超阈值：只有 2 个文件（哪怕很小也不值得起一次重写）
        List<DataFile> fewFiles = List.of(
                new DataFile("2024-06-01/part-01.parquet", "2024-06-01", 10_000L, 100_000L),
                new DataFile("2024-06-01/part-02.parquet", "2024-06-01", 10_000L, 100_000L));
        // 平均大小已达标：5 个文件、每个 50KB（文件数超了阈值，但合并没有字节收益）
        List<DataFile> bigEnough = new ArrayList<>();
        for (int i = 1; i <= 5; i++) {
            bigEnough.add(new DataFile(String.format("2024-06-02/part-%02d.parquet", i),
                    "2024-06-02", 5_000L, 50_000L));
        }

        AtomicInteger pass = new AtomicInteger();

        Compaction.Plan plan = Compaction.plan(smallPartition, smallFiles, targetBytes, minFiles);
        List<DataFile> merged = Compaction.apply(smallFiles, plan);

        // 1) 小文件分区产出非空方案：10 个小文件 → 2 个目标大小文件
        check(pass, !plan.isNoop()
                        && plan.fileCountBefore() == 10
                        && plan.fileCountAfter() == 2
                        && plan.bytesBefore() == 10_000L,
                "小文件分区产出非空方案：10 个 1KB 文件 → 合并为 2 个文件（targetBytes="
                        + targetBytes + ", minFiles=" + minFiles + "）");

        // 2) 合并后文件数下降：apply 真的减少了打开文件数
        check(pass, merged.size() == plan.fileCountAfter() && merged.size() < plan.fileCountBefore(),
                "合并后文件数下降：apply 后 " + merged.size() + " 个文件 < 合并前 "
                        + plan.fileCountBefore() + " 个");

        // 3) readSavedRatio > 0，且精确等于 readCost 口径算出的值
        long readBefore = Compaction.readCost(plan.bytesBefore(), plan.fileCountBefore());
        long readAfter = Compaction.readCost(plan.bytesAfter(), plan.fileCountAfter());
        double expectedSaved = (readBefore - readAfter) / (double) readBefore;
        check(pass, plan.readSavedRatio() > 0.0
                        && Math.abs(plan.readSavedRatio() - expectedSaved) < 1e-12,
                String.format("readSavedRatio > 0 且口径一致：%.4f（读取代价 %,d → %,d，含每文件 %d 字节打开开销）",
                        plan.readSavedRatio(), readBefore, readAfter,
                        Compaction.OPEN_COST_BYTES_PER_FILE));

        // 4) 合并后总字节数为「压缩后字节」：示例口径是不压缩字节，bytesAfter == bytesBefore
        long mergedBytes = merged.stream().mapToLong(DataFile::bytes).sum();
        long mergedRows = merged.stream().mapToLong(DataFile::rows).sum();
        check(pass, mergedBytes == plan.bytesAfter() && mergedBytes == plan.bytesBefore()
                        && mergedRows == 1_000L,
                "合并后总字节数 = 方案 bytesAfter = " + mergedBytes
                        + "（口径：合并只重排不压缩字节，收益来自打开文件数下降），行数守恒 " + mergedRows);

        // 5) 重复 apply 结果一致：同输入两次输出逐项相等；对合并结果再 plan 得到空方案，apply 原样返回
        List<DataFile> mergedAgain = Compaction.apply(smallFiles, plan);
        Compaction.Plan secondPlan = Compaction.plan(smallPartition, merged, targetBytes, minFiles);
        List<DataFile> afterSecondPass = Compaction.apply(merged, secondPlan);
        check(pass, merged.equals(mergedAgain)
                        && secondPlan.isNoop()
                        && afterSecondPass.equals(merged),
                "重复 apply 结果一致（幂等）：同输入两次 apply 相等；对合并结果再 plan 为空方案，二次 apply 不再改动");

        // 6) 不需要合并的分区返回空方案：文件数 <= minFiles，或平均大小已达标
        Compaction.Plan fewPlan = Compaction.plan("2024-06-01", fewFiles, targetBytes, minFiles);
        Compaction.Plan bigPlan = Compaction.plan("2024-06-02", bigEnough, targetBytes, minFiles);
        check(pass, fewPlan.isNoop() && fewPlan.readSavedRatio() == 0.0
                        && fewPlan.fileCountBefore() == 2
                        && bigPlan.isNoop() && bigPlan.readSavedRatio() == 0.0
                        && bigPlan.fileCountBefore() == 5,
                "不需要合并的分区返回空方案：2024-06-01（2 个文件 ≤ minFiles）、"
                        + "2024-06-02（平均 50,000 字节 ≥ targetBytes）");

        // 7) 合并后的文件大小接近 targetBytes：每个文件 <= target 且 >= target/2（避免又产生一批小文件）
        boolean sizesOk = true;
        for (DataFile f : merged) {
            if (f.bytes() > targetBytes || f.bytes() < targetBytes / 2) {
                sizesOk = false;
            }
        }
        check(pass, sizesOk,
                "合并后文件大小接近 targetBytes：每个文件都在 [" + (targetBytes / 2) + ", "
                        + targetBytes + "] 字节内，不会立刻又变成小文件");

        System.out.println("== compaction 收益测算 ==");
        System.out.printf("  分区 %s: 文件 %d -> %d，字节 %,d -> %,d，readSavedRatio=%.4f%n",
                plan.partition(), plan.fileCountBefore(), plan.fileCountAfter(),
                plan.bytesBefore(), plan.bytesAfter(), plan.readSavedRatio());
        System.out.printf("  合并后文件：%s%n", merged);

        if (pass.get() == TOTAL) {
            System.out.printf("ALL PASS: %d/%d%n", pass.get(), TOTAL);
        } else {
            System.out.printf("FAILED: %d/%d（详见上面的 FAIL 行）%n", pass.get(), TOTAL);
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
