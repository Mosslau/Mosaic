// languages/java/ph23-lakehouse-orchestration/examples/ex03-partition-layout/PartitionLayoutDemo.java —— 分区布局主入口：裁剪收益 + 小文件检测
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex03 *.java && java -cp /tmp/ph23-ex03 PartitionLayoutDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
//
// 场景：21 天的实例事件表，其中 20 天是正常的两个大文件，最后一天因流式写入留下 10 个 1KB 小文件
// （小文件灾难的现场）。断言覆盖 3.3：裁剪比例、按日期裁剪、无过滤=全表、小文件分区检测、
// scanBytes 与逐文件求和一致、未命中分区为空。
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class PartitionLayoutDemo {

    private static final int TOTAL = 7;

    public static void main(String[] args) {
        PartitionLayout layout = new PartitionLayout();

        // 20 天常规分区：每天 2 个 10 万字节 / 1 万行的文件
        for (int day = 1; day <= 20; day++) {
            String p = String.format("2024-06-%02d", day);
            for (int f = 1; f <= 2; f++) {
                layout.add(new DataFile(p + "/part-" + f + ".parquet", p, 10_000L, 100_000L));
            }
        }
        // 第 21 天：流式写入 + 频繁提交留下 10 个 1KB 小文件（读时要打开 10 次，写时很省事）
        String tinyDay = "2024-06-21";
        for (int f = 1; f <= 10; f++) {
            layout.add(new DataFile(String.format("%s/part-%02d.parquet", tinyDay, f),
                    tinyDay, 100L, 1_000L));
        }

        AtomicInteger pass = new AtomicInteger();

        long full = layout.fullScanBytes();
        PartitionLayout.ScanResult day15 = layout.scan("2024-06-15");
        double ratio = layout.pruningRatio("2024-06-15");

        // 1) 全表字节数 > 裁剪后字节数，且裁剪比例 >= 0.9（21 天里查 1 天，理想值约 95%）
        check(pass, full == 4_010_000L && day15.scanBytes() < full && ratio >= 0.9,
                String.format("全表扫描 %,d 字节 vs 单日裁剪后 %,d 字节，裁剪比例 %.4f ≥ 0.9",
                        full, day15.scanBytes(), ratio));

        // 2) 按日期裁剪只命中该分区：返回文件的 partition 全等于 filter，行数也对得上
        boolean onlyThatPartition = !day15.files().isEmpty();
        long rowsHit = 0L;
        for (DataFile f : day15.files()) {
            if (!f.partition().equals("2024-06-15")) {
                onlyThatPartition = false;
            }
            rowsHit += f.rows();
        }
        check(pass, onlyThatPartition && day15.fileCount() == 2 && rowsHit == 20_000L,
                "按日期裁剪只命中该分区：2024-06-15 返回 2 个文件 / 20,000 行，无跨分区文件");

        // 3) 无过滤时为全表：* 与 null 都代表不裁剪
        PartitionLayout.ScanResult allStar = layout.scan(PartitionLayout.ALL_PARTITIONS);
        PartitionLayout.ScanResult allNull = layout.scan(null);
        check(pass, allStar.fileCount() == layout.fileCount()
                        && allStar.scanBytes() == full
                        && allNull.scanBytes() == full,
                "无过滤时为全表：\"*\" 与 null 都返回全部 " + layout.fileCount() + " 个文件 / "
                        + String.format("%,d", full) + " 字节");

        // 4) 小文件分区检测正确：只有第 21 天满足「文件数 > 3 且平均 < 50KB」
        List<String> small = layout.smallFilePartitions(3, 50_000L);
        check(pass, small.equals(List.of(tinyDay)),
                "小文件分区检测正确：smallFilePartitions(3, 50_000) = " + small
                        + "（第 21 天 10 个文件、平均 1,000 字节）");

        // 5) scanBytes 等于命中文件字节之和（逐文件求和与返回值一致）
        long manualSum = day15.files().stream().mapToLong(DataFile::bytes).sum();
        check(pass, manualSum == day15.scanBytes() && manualSum == layout.scanBytes("2024-06-15"),
                "scanBytes 等于命中文件字节之和：逐文件求和 " + manualSum + " == scan() 返回 "
                        + day15.scanBytes());

        // 6) 裁剪比例计算正确，且无参版本按「最新分区」口径给出同一个值
        double expected = 1.0 - (double) day15.scanBytes() / (double) full;
        double latestRatio = layout.pruningRatio();
        double expectedLatest = 1.0 - 10_000.0 / (double) full;
        check(pass, Math.abs(ratio - expected) < 1e-12
                        && Math.abs(latestRatio - expectedLatest) < 1e-12,
                String.format("裁剪比例计算正确：1 - %d/%d = %.6f（无参版本按最新分区 = %.6f）",
                        day15.scanBytes(), full, expected, latestRatio));

        // 7) 未命中分区返回空：过滤一个不存在的日期既不该报错，也要给出 100% 裁剪
        PartitionLayout.ScanResult miss = layout.scan("2024-07-01");
        check(pass, miss.fileCount() == 0 && miss.scanBytes() == 0L
                        && layout.pruningRatio("2024-07-01") == 1.0,
                "未命中分区返回空：2024-07-01 返回 0 文件 / 0 字节，裁剪比例 1.0");

        System.out.println("== 分区扫描量对比 ==");
        System.out.printf("  全表            : %,d 字节 / %d 个文件%n", full, layout.fileCount());
        System.out.printf("  裁剪到 2024-06-15: %,d 字节 / %d 个文件（比例 %.4f）%n",
                day15.scanBytes(), day15.fileCount(), ratio);
        System.out.printf("  小文件分区       : %s%n", small);

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
