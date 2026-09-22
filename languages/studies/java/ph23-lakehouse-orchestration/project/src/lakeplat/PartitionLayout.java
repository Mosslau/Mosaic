// project/src/lakeplat/PartitionLayout.java —— 分区布局：裁剪、扫描字节估算、小文件检测
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

/**
 * 分区布局（主文档 3.3）：把「查询谓词」翻译成「要打开的文件列表」，并给出扫描成本读数。
 *
 * <p>核心判据是一句话：**分区键要匹配查询谓词**。裁剪收益必须能被看到——
 * {@link ScanCost#pruneRatio()} 就是「这次分区设计值不值」的直接读数，也是 3.8 成本一屏的基础。
 *
 * <p>小文件检测阈值（主文档 3.3 末段）：
 * {@code 分区内文件数 > minFilesPerPartition 且 平均文件大小 < smallFileThresholdBytes}
 * → 该分区需要 compaction。
 */
public final class PartitionLayout {

    /** 一次扫描的成本读数：打开文件数 + 扫描字节数 + 命中分区数。 */
    public record ScanCost(int files, long bytes, int partitions, long fullBytes, int fullFiles) {
        /** 裁剪后扫描字节相对全表扫描的占比（0.9 = 省掉 90%）。 */
        public double pruneRatio() {
            return fullBytes == 0 ? 0.0 : 1.0 - bytes * 1.0 / fullBytes;
        }

        /** 展示成一行，便于日志与断言输出。 */
        public String label() {
            return "扫描 " + files + "/" + fullFiles + " 个文件、" + bytes + "/" + fullBytes
                    + " 字节（裁剪 " + String.format("%.1f", pruneRatio() * 100) + "%）";
        }
    }

    /** 被标记为「小文件分区」的读数。 */
    public record SmallFileFlag(String partition, int fileCount, long totalBytes, long averageBytes, String reason) {

        @Override
        public String toString() {
            return partition + " 文件 " + fileCount + " 个 / 平均 " + averageBytes + "B（" + reason + "）";
        }
    }

    private final String partitionKey;
    private final int minFilesPerPartition;
    private final long smallFileThresholdBytes;

    public PartitionLayout(String partitionKey, int minFilesPerPartition, long smallFileThresholdBytes) {
        this.partitionKey = partitionKey;
        this.minFilesPerPartition = minFilesPerPartition;
        this.smallFileThresholdBytes = smallFileThresholdBytes;
    }

    public String partitionKey() {
        return partitionKey;
    }

    public int minFilesPerPartition() {
        return minFilesPerPartition;
    }

    public long smallFileThresholdBytes() {
        return smallFileThresholdBytes;
    }

    /** 分区值 → 规范分区名（`event_date=2024-06-01`）。 */
    public String partitionName(String partitionValue) {
        return partitionValue.contains("=") ? partitionValue : partitionKey + "=" + partitionValue;
    }

    /** 全表扫描：不裁剪（对照基准）。 */
    public ScanCost fullScan(List<DataFile> all) {
        long bytes = all.stream().mapToLong(DataFile::bytes).sum();
        long partitions = all.stream().map(DataFile::partition).distinct().count();
        return new ScanCost(all.size(), bytes, (int) partitions, bytes, all.size());
    }

    /** 分区裁剪：只保留命中分区谓词的文件，返回成本读数。 */
    public ScanCost scan(List<DataFile> all, Set<String> partitionPredicate) {
        List<DataFile> hit = prune(all, partitionPredicate);
        long bytes = hit.stream().mapToLong(DataFile::bytes).sum();
        long partitions = hit.stream().map(DataFile::partition).distinct().count();
        long fullBytes = all.stream().mapToLong(DataFile::bytes).sum();
        return new ScanCost(hit.size(), bytes, (int) partitions, fullBytes, all.size());
    }

    /** 裁剪后的文件列表（分区值可写 `2024-06-01` 或 `event_date=2024-06-01`）。 */
    public List<DataFile> prune(List<DataFile> all, Set<String> partitionPredicate) {
        List<DataFile> hit = new ArrayList<>();
        for (DataFile file : all) {
            String name = partitionName(file.partition());
            if (partitionPredicate.contains(name) || partitionPredicate.contains(file.partitionValue())) {
                hit.add(file);
            }
        }
        return List.copyOf(hit);
    }

    /** 按分区归组（分区名字典序）。 */
    public Map<String, List<DataFile>> group(List<DataFile> all) {
        Map<String, List<DataFile>> grouped = new TreeMap<>();
        for (DataFile file : all) {
            grouped.computeIfAbsent(partitionName(file.partition()), key -> new ArrayList<>()).add(file);
        }
        Map<String, List<DataFile>> frozen = new TreeMap<>();
        grouped.forEach((partition, files) -> frozen.put(partition, List.copyOf(files)));
        return Collections.unmodifiableMap(frozen);
    }

    /** 小文件检测：返回需要 compaction 的分区（分区名字典序）。 */
    public List<SmallFileFlag> detectSmallFilePartitions(List<DataFile> all) {
        List<SmallFileFlag> flags = new ArrayList<>();
        group(all).forEach((partition, files) -> {
            long bytes = files.stream().mapToLong(DataFile::bytes).sum();
            long average = bytes / files.size();
            if (files.size() > minFilesPerPartition && average < smallFileThresholdBytes) {
                flags.add(new SmallFileFlag(partition, files.size(), bytes, average,
                        "文件数 " + files.size() + " > " + minFilesPerPartition
                                + " 且平均 " + average + "B < 目标 " + smallFileThresholdBytes + "B"));
            }
        });
        return List.copyOf(flags);
    }
}
