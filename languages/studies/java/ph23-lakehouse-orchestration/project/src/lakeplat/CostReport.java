// project/src/lakeplat/CostReport.java —— 成本度量：扫描量 / 存储量 / 小文件数 / compaction 收益
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 成本度量（主文档 3.8）：数据平台第三道兜底——**代价可见**。
 *
 * <p>四个读数就是治理动作的全部依据：扫描量（按扫描计费）、存储量、小文件数、compaction 收益。
 * 没有度量的治理动作都是拍脑袋，所以本类刻意只做「把已有读数汇总成一份快照」，
 * 不发明任何自己的数字——{@link #snapshot} 的每个字段都来自表的清单与 {@link PartitionLayout} 的检测结果。
 */
public final class CostReport {

    /** 一张表的成本读数。 */
    public record TableCost(String table, String layer, int partitions, int files, long bytes,
                            int smallFilePartitions) {
        public long bytesPerFile() {
            return files == 0 ? 0 : bytes / files;
        }
    }

    /** 全平台成本一屏的数据源（与 {@code OpsConsole} 共用，保证人看的与机器抓的同源）。 */
    public record Snapshot(List<TableCost> tables, long scanBytes, long scanBytesFull, long storageBytes,
                           int fileCount, int partitionCount, int smallFilePartitions,
                           int compactionPlannedPartitions, double compactionReadSavedRatio) {
        public double scanSavedRatio() {
            return scanBytesFull == 0 ? 0.0 : 1.0 - scanBytes * 1.0 / scanBytesFull;
        }

        public double averageFileBytes() {
            return fileCount == 0 ? 0.0 : storageBytes * 1.0 / fileCount;
        }

        public String label() {
            return "表 " + tables.size() + " 张 / 分区 " + partitionCount + " 个 / 文件 " + fileCount
                    + " 个 / 存储 " + storageBytes + "B / 小文件分区 " + smallFilePartitions
                    + " / compaction 增益 " + String.format("%.1f", compactionReadSavedRatio * 100) + "%";
        }
    }

    private final WarehouseModel model;

    public CostReport(WarehouseModel model) {
        this.model = model;
    }

    /**
     * 汇总当前成本快照。
     *
     * @param filesByTable 每张表当前的文件清单
     * @param scanBytes    本次查询实际扫描的字节数（分区裁剪后）
     * @param scanFullBytes 全表扫描的字节数（裁剪前的对照基准）
     * @param layout       分区布局（用于小文件检测阈值）
     * @param plans        compaction 方案（分区名 → 方案）
     */
    public Snapshot snapshot(Map<TableRef, List<DataFile>> filesByTable, long scanBytes, long scanFullBytes,
                             PartitionLayout layout, Map<String, Compaction.Plan> plans) {
        List<TableCost> costs = new ArrayList<>();
        long storage = 0;
        int files = 0;
        int partitions = 0;
        int smallFilePartitions = 0;
        for (Map.Entry<TableRef, List<DataFile>> entry : new LinkedHashMap<>(filesByTable).entrySet()) {
            TableRef table = model.require(entry.getKey());
            List<DataFile> tableFiles = entry.getValue();
            long bytes = tableFiles.stream().mapToLong(DataFile::bytes).sum();
            Map<String, List<DataFile>> grouped = layout.group(tableFiles);
            int small = layout.detectSmallFilePartitions(tableFiles).size();
            costs.add(new TableCost(table.table(), table.layer().name(), grouped.size(),
                    tableFiles.size(), bytes, small));
            storage += bytes;
            files += tableFiles.size();
            partitions += grouped.size();
            smallFilePartitions += small;
        }
        double readSaved = plans.values().stream()
                .mapToDouble(Compaction.Plan::readSavedRatio)
                .average()
                .orElse(0.0);
        return new Snapshot(List.copyOf(costs), scanBytes, scanFullBytes, storage, files, partitions,
                smallFilePartitions, plans.size(), readSaved);
    }

    /** 每张表的成本读数（一屏的「表」块）。 */
    public List<TableCost> tableCosts(Map<TableRef, List<DataFile>> filesByTable, PartitionLayout layout) {
        return snapshot(filesByTable, 0, 0, layout, Map.of()).tables();
    }

    /** 供人阅读的行（审计与 README 用）。 */
    public static String line(TableCost cost) {
        return String.format("%-10s [%s] 分区 %d / 文件 %d / 存储 %dB / 小文件分区 %d",
                cost.table(), cost.layer(), cost.partitions(), cost.files(), cost.bytes(),
                cost.smallFilePartitions());
    }
}
