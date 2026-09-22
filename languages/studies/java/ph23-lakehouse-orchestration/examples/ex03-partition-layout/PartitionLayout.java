// languages/java/ph23-lakehouse-orchestration/examples/ex03-partition-layout/PartitionLayout.java —— 分区布局：裁剪扫描 + 扫描字节估算 + 小文件检测
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex03 *.java && java -cp /tmp/ph23-ex03 PartitionLayoutDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
//
// 为什么 scanBytes 是这个类的第一公民：扫描字节数就是「这次查询要付多少钱」（按扫描量计费的引擎、
// 按 IO 计费的存储都以此为准）。分区设计的好坏不必争论——把裁剪前的全表字节与裁剪后的字节并排
// 打印出来，一眼就能看出分区键选得对不对。
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class PartitionLayout {

    /** 全表扫描的过滤符：显式常量，避免把 null 当成「无过滤」的隐式约定散落在调用方。 */
    public static final String ALL_PARTITIONS = "*";

    /**
     * 一次扫描的结果。
     *
     * @param files     命中分区的文件（按路径排序，保证可复现）
     * @param scanBytes 这些文件的字节总和 = 本次查询的扫描量
     */
    public record ScanResult(List<DataFile> files, long scanBytes) {
        public ScanResult {
            files = List.copyOf(files);
        }

        public int fileCount() {
            return files.size();
        }
    }

    private final List<DataFile> files = new ArrayList<>();

    public void add(DataFile file) {
        files.add(file);
    }

    public int fileCount() {
        return files.size();
    }

    /** 已注册的分区（升序）。 */
    public List<String> partitions() {
        return files.stream().map(DataFile::partition).distinct().sorted().toList();
    }

    /**
     * 按分区谓词扫描。filter 为 null / 空白 / {@link #ALL_PARTITIONS} 时代表无过滤（全表）。
     * 返回的 scanBytes 就是「裁剪后要读的字节」。
     */
    public ScanResult scan(String partitionFilter) {
        boolean all = partitionFilter == null || partitionFilter.isBlank()
                || ALL_PARTITIONS.equals(partitionFilter);
        List<DataFile> hit = new ArrayList<>();
        long bytes = 0L;
        for (DataFile f : files) {
            if (all || f.partition().equals(partitionFilter)) {
                hit.add(f);
                bytes += f.bytes();
            }
        }
        hit.sort(Comparator.comparing(DataFile::path));
        return new ScanResult(hit, bytes);
    }

    public long scanBytes(String partitionFilter) {
        return scan(partitionFilter).scanBytes();
    }

    /** 裁剪前的全表字节数：与 scanBytes 相减就是分区裁剪省下的钱。 */
    public long fullScanBytes() {
        return files.stream().mapToLong(DataFile::bytes).sum();
    }

    /**
     * 小文件分区检测：文件数 > maxFiles 且 平均文件大小 < minAvgBytes 的分区需要 compaction。
     * 两个条件缺一不可——文件多但每个都很大（正常分片）不需要合并；文件少且小（小表）也不值得起一次重写。
     *
     * @return 需要 compaction 的分区名（升序）
     */
    public List<String> smallFilePartitions(int maxFiles, long minAvgBytes) {
        List<String> small = new ArrayList<>();
        for (Map.Entry<String, List<DataFile>> e : groupByPartition().entrySet()) {
            int n = e.getValue().size();
            long bytes = e.getValue().stream().mapToLong(DataFile::bytes).sum();
            long avg = bytes / n;
            if (n > maxFiles && avg < minAvgBytes) {
                small.add(e.getKey());
            }
        }
        Collections.sort(small);
        return List.copyOf(small);
    }

    /**
     * 裁剪比例 = 1 - 命中分区字节 / 全表字节。
     * 无过滤或空表时返回 0（没有任何裁剪收益可言）。
     */
    public double pruningRatio(String partitionFilter) {
        long full = fullScanBytes();
        if (full == 0L) {
            return 0.0;
        }
        return 1.0 - (double) scanBytes(partitionFilter) / (double) full;
    }

    /**
     * 无参版本：按「最新分区」这一最常见的分析谓词（如"看最近一天"）计算裁剪比例。
     * 显式声明这个约定，而不是偷偷选一个分区，避免读代码的人误解数字口径。
     */
    public double pruningRatio() {
        List<String> ps = partitions();
        if (ps.isEmpty()) {
            return 0.0;
        }
        return pruningRatio(ps.get(ps.size() - 1));
    }

    private Map<String, List<DataFile>> groupByPartition() {
        Map<String, List<DataFile>> byPartition = new LinkedHashMap<>();
        for (DataFile f : files) {
            byPartition.computeIfAbsent(f.partition(), k -> new ArrayList<>()).add(f);
        }
        return byPartition;
    }
}
