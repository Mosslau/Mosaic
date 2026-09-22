// languages/java/ph23-lakehouse-orchestration/examples/ex08-quality-lineage-cost/CostReport.java —— 成本一屏与 Prometheus 文本：扫描字节（裁剪前后）、存储字节、小文件分区数、门禁通过率
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex08 *.java && java -cp /tmp/ph23-ex08 QualityLineageCostDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：9/9 PASS）
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.TreeSet;

/**
 * 成本一屏的数据源：分区文件清单 + 一次查询的分区裁剪谓词 + 门禁通过率。
 *
 * 三个数字回答三个问题（3.3 / 3.4 / 3.8）：
 *   - `scanBytesBefore` vs `scanBytesAfter`：这次查询要付多少钱，分区设计好不好一眼可见；
 *   - `storageBytes` / `smallFilePartitions`：存储与元数据债有多大，哪些分区该 compaction；
 *   - `gatePassRate`：数据可不可信（门禁拦下了多少次提交）。
 *
 * 两个输出（一屏文本 + Prometheus 文本）**都由同一个 CostReport 对象渲染**——所以「一屏与指标同源」
 * 是一个结构性事实，而不是靠人工对齐：数值来自同一批字段，不可能对不上。
 * 指标名统一 `lake_` 前缀，语法遵循 `# HELP` / `# TYPE` / `name{label="v"} value`。
 */
public record CostReport(
        long scanBytesBefore,
        long scanBytesAfter,
        long storageBytes,
        long smallFilePartitions,
        long totalPartitions,
        long gateCommits,
        long gateRejections,
        Map<String, Long> scanBytesByPartition) {

    /** 小文件判定阈值：分区内平均文件 < 64MB 且文件数 > 2 → 该分区需要 compaction（与 ex03/ex04 同口径）。 */
    public static final long SMALL_FILE_TARGET_BYTES = 64L * 1024 * 1024;
    public static final int SMALL_FILE_MIN_COUNT = 2;

    /** 一个数据文件：分区 + 行数 + 字节数。 */
    public record DataFile(String path, String partition, long rows, long bytes) {
        public DataFile {
            if (partition == null || partition.isBlank()) {
                throw new IllegalArgumentException("分区不能为空");
            }
            if (bytes < 0 || rows < 0) {
                throw new IllegalArgumentException("行数与字节数不能为负：" + rows + "/" + bytes);
            }
        }
    }

    public CostReport {
        if (scanBytesBefore < 0 || scanBytesAfter < 0 || storageBytes < 0
                || smallFilePartitions < 0 || totalPartitions < 0 || gateCommits < 0 || gateRejections < 0) {
            throw new IllegalArgumentException("成本指标不能为负");
        }
        if (scanBytesAfter > scanBytesBefore) {
            throw new IllegalArgumentException("裁剪后的扫描字节不可能大于裁剪前："
                    + scanBytesAfter + " > " + scanBytesBefore);
        }
        scanBytesByPartition = Map.copyOf(scanBytesByPartition);
    }

    /**
     * 由文件清单 + 查询谓词（要扫哪些分区）构建报告。
     * 「裁剪前」= 全表所有文件字节和；「裁剪后」= 只命中谓词分区的文件字节和；
     * 存储字节 = 同一批文件的字节和（示例把「存储」与「扫描前」设为同一来源，避免两个数字口径不一）。
     */
    public static CostReport build(List<DataFile> files, List<String> queryPartitions,
                                   long gateCommits, long gateRejections) {
        TreeSet<String> wanted = new TreeSet<>(queryPartitions);
        Map<String, Long> byPartition = new TreeMap<>();
        long before = 0;
        long after = 0;
        for (DataFile file : files) {
            byPartition.merge(file.partition(), file.bytes(), Long::sum);
            before += file.bytes();
            if (wanted.contains(file.partition())) {
                after += file.bytes();
            }
        }
        long smallPartitions = 0;
        for (Map.Entry<String, Long> entry : byPartition.entrySet()) {
            int fileCount = 0;
            for (DataFile file : files) {
                if (file.partition().equals(entry.getKey())) {
                    fileCount++;
                }
            }
            long average = fileCount == 0 ? 0 : entry.getValue() / fileCount;
            if (fileCount > SMALL_FILE_MIN_COUNT && average < SMALL_FILE_TARGET_BYTES) {
                smallPartitions++;
            }
        }
        return new CostReport(before, after, before, smallPartitions, byPartition.size(),
                gateCommits, gateRejections, byPartition);
    }

    public long scanBytesSaved() {
        return scanBytesBefore - scanBytesAfter;
    }

    /** 裁剪收益：分区裁剪让扫描量下降的比例（0~1）。总量为 0 时定义为 0，不出现 NaN。 */
    public double scanSavedRatio() {
        return scanBytesBefore == 0 ? 0.0 : scanBytesSaved() / (double) scanBytesBefore;
    }

    /** 门禁通过率（百分比）。 */
    public double gatePassRatePct() {
        long attempts = gateCommits + gateRejections;
        return attempts == 0 ? 0.0 : gateCommits * 100.0 / attempts;
    }

    /** ① 运维一屏：扫描 / 存储 / 小文件 / 门禁四块。 */
    public String renderScreen() {
        StringBuilder sb = new StringBuilder();
        sb.append("+--------------------- 湖仓成本与质量一屏 ---------------------+\n");
        sb.append(String.format(" [扫描]   裁剪前 %s → 裁剪后 %s（省 %.1f%%）%n",
                human(scanBytesBefore), human(scanBytesAfter), scanSavedRatio() * 100));
        sb.append(String.format(" [存储]   %s（扫描/存储 = %.2f）%n",
                human(storageBytes), storageBytes == 0 ? 0.0 : scanBytesBefore / (double) storageBytes));
        sb.append(String.format(" [小文件] %d/%d 个分区低于阈值，需 compaction%n",
                smallFilePartitions, totalPartitions));
        sb.append(String.format(" [门禁]   通过率 %.1f%%（提交 %d / 拒绝 %d）%n",
                gatePassRatePct(), gateCommits, gateRejections));
        sb.append("+--------------------------------------------------------------+\n");
        return sb.toString();
    }

    /**
     * ② Prometheus 文本指标：4 个指标族、6 条样本行。
     * 全部数值都取自本对象的字段，因此与 {@link #renderScreen()} 同源。
     */
    public String renderPrometheus() {
        StringBuilder sb = new StringBuilder();
        family(sb, "lake_scan_bytes", "一次查询的扫描字节数（分区裁剪前后）", "gauge");
        sb.append("lake_scan_bytes{stage=\"before\"} ").append(scanBytesBefore).append('\n');
        sb.append("lake_scan_bytes{stage=\"after\"} ").append(scanBytesAfter).append('\n');

        family(sb, "lake_storage_bytes", "表在对象存储上的存储字节数", "gauge");
        sb.append("lake_storage_bytes ").append(storageBytes).append('\n');

        family(sb, "lake_small_file_partitions", "低于小文件阈值的分区数", "gauge");
        sb.append("lake_small_file_partitions ").append(smallFilePartitions).append('\n');

        family(sb, "lake_gate_failures_total", "被质量门禁拒绝的提交次数", "counter");
        sb.append("lake_gate_failures_total ").append(gateRejections).append('\n');
        return sb.toString();
    }

    /** 指标族声明（# HELP + # TYPE），必须先于该族的样本行输出。 */
    private static void family(StringBuilder sb, String name, String help, String type) {
        sb.append("# HELP ").append(name).append(' ').append(help).append('\n');
        sb.append("# TYPE ").append(name).append(' ').append(type).append('\n');
    }

    /** 本报告暴露的指标族（Prometheus 文本里应各有且仅有一组 HELP/TYPE）。 */
    public static List<String> families() {
        return List.of("lake_scan_bytes", "lake_storage_bytes", "lake_small_file_partitions",
                "lake_gate_failures_total");
    }

    /** 分区级扫描字节明细（Prometheus 里没有拆到分区，但一屏/断言要能看）。 */
    public String renderPartitionScan() {
        List<String> lines = new ArrayList<>();
        scanBytesByPartition.forEach((partition, bytes) -> lines.add(partition + "=" + human(bytes)));
        return String.join(" | ", lines);
    }

    /** 人类可读的字节数（一屏用；指标文本里保持原始整数，别让展示格式污染机器可读输出）。 */
    public static String human(long bytes) {
        if (bytes >= 1024L * 1024 * 1024) {
            return String.format("%.1fGB", bytes / (1024.0 * 1024 * 1024));
        }
        if (bytes >= 1024L * 1024) {
            return String.format("%.0fMB", bytes / (1024.0 * 1024));
        }
        if (bytes >= 1024L) {
            return String.format("%.0fKB", bytes / 1024.0);
        }
        return bytes + "B";
    }
}
