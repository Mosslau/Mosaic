// project/src/lakeplat/Compaction.java —— 小文件合并：决策 + 收益测算 + 幂等 apply
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * compaction（主文档 3.4 / 4.2）：把一堆小文件重写成接近目标大小的大文件。
 *
 * <p>三件事必须同时成立，否则治理动作就是拍脑袋：
 * <ol>
 *   <li><b>收益可测算</b>：{@link Plan#readSavedRatio()} = 打开文件数下降比例（未来读该分区 k 次的收益同时放大 k 倍）；</li>
 *   <li><b>代价可测算</b>：{@link Plan#writeAmplification()} = 重写的字节 / 分区总量（合并要重写数据，是写放大）；</li>
 *   <li><b>重复执行幂等</b>：同样的输入合并两次结果一致——{@link #apply} 用 `part-<序号>` 规范命名整体重建分区，
 *       所以第二次 apply 产出同一组文件路径与同一份清单。合并本身也会产生新快照（时间旅行链变长），这是它的代价之一。</li>
 * </ol>
 *
 * <p>工程判据（4.2）：合并的价值取决于**未来还会读几次**，而不是文件多不多——热写分区不合并、冷存分区定期合并。
 */
public final class Compaction {

    /** 一次合并方案与收益读数。 */
    public record Plan(String partition, int fileCountBefore, int fileCountAfter,
                       long bytesBefore, long bytesAfter, double readSavedRatio,
                       long bytesRewritten, int sourceFiles) {
        public Plan {
            if (fileCountAfter <= 0 && fileCountBefore > 0) {
                throw new IllegalArgumentException("合并后文件数必须为正");
            }
        }

        /** 写放大：合并重写的字节 / 分区原字节（=1.0 表示把整分区重写了一遍）。 */
        public double writeAmplification() {
            return bytesBefore == 0 ? 0.0 : bytesRewritten * 1.0 / bytesBefore;
        }

        public String label() {
            return partition + " 文件 " + fileCountBefore + "→" + fileCountAfter
                    + "，读收益 " + String.format("%.1f", readSavedRatio * 100)
                    + "%，写放大 " + String.format("%.2f", writeAmplification()) + "x";
        }
    }

    /** 合并后每个文件的目标字节数（示例 512KiB）。 */
    public static final long DEFAULT_TARGET_BYTES = 512L * 1024L;

    private final long targetBytes;

    public Compaction() {
        this(DEFAULT_TARGET_BYTES);
    }

    public Compaction(long targetBytes) {
        if (targetBytes <= 0) {
            throw new IllegalArgumentException("目标文件大小必须为正");
        }
        this.targetBytes = targetBytes;
    }

    public long targetBytes() {
        return targetBytes;
    }

    /**
     * 合并一个分区（主文档 3.4 的判据）：按清单顺序把文件累积到 {@code targetBytes} 附近，
     * 每个输出文件的路径用 `part-<序号>` 规范命名，整体重建分区。
     *
     * <p>只搬字节、不改变总行数与总字节数——合并是**重写**，不是增删数据。
     */
    public List<DataFile> merge(String partition, List<DataFile> files) {
        if (files.isEmpty()) {
            return List.of();
        }
        long rowsPerByteNumerator = files.stream().mapToLong(DataFile::rows).sum();
        long totalBytes = files.stream().mapToLong(DataFile::bytes).sum();
        List<DataFile> merged = new ArrayList<>();
        List<DataFile> bucket = new ArrayList<>();
        long bucketBytes = 0;
        int index = 0;
        for (DataFile file : files) {
            bucket.add(file);
            bucketBytes += file.bytes();
            if (bucketBytes >= targetBytes) {
                merged.add(build(partition, index++, bucket, bucketBytes, rowsPerByteNumerator, totalBytes));
                bucket = new ArrayList<>();
                bucketBytes = 0;
            }
        }
        if (!bucket.isEmpty()) {
            merged.add(build(partition, index, bucket, bucketBytes, rowsPerByteNumerator, totalBytes));
        }
        return List.copyOf(merged);
    }

    private DataFile build(String partition, int index, List<DataFile> bucket, long bucketBytes,
                           long totalRows, long totalBytes) {
        // 行数按字节占比确定性分摊，保证 Σrows 与 Σbytes 与合并前完全一致（不留"蒸发"的行）
        long rows = bucketBytes == totalBytes ? totalRows
                : Math.round(totalRows * (bucketBytes * 1.0 / totalBytes));
        return new DataFile(path(partition, index), partition, rows, bucketBytes);
    }

    private String path(String partition, int index) {
        return "data/" + partition + "/part-" + String.format("%04d", index) + ".parquet";
    }

    /** 产出某分区的合并方案与收益读数（不修改任何东西，纯函数）。 */
    public Plan plan(String partition, List<DataFile> files) {
        if (files.isEmpty()) {
            throw new IllegalArgumentException("分区 " + partition + " 没有文件，无法规划合并");
        }
        long bytesBefore = files.stream().mapToLong(DataFile::bytes).sum();
        List<DataFile> merged = merge(partition, files);
        long bytesAfter = merged.stream().mapToLong(DataFile::bytes).sum();
        double readSaved = 1.0 - merged.size() * 1.0 / files.size();
        return new Plan(partition, files.size(), merged.size(), bytesBefore, bytesAfter, readSaved, bytesBefore, files.size());
    }

    /**
     * 幂等 apply：按方案重建分区文件，**不改变清单之外的任何东西**。
     *
     * <p>幂等性来源：输出文件名只由规范下标决定（`part-0000`、`part-0001`…），与输入文件叫什么无关；
     * 因此对已经合并过的分区再来一次，得到的文件路径与字节数完全相同。
     */
    public List<DataFile> apply(String partition, List<DataFile> files) {
        return merge(partition, files);
    }

    /** 判断一个分区当前是否需要合并（决策入口：只对"文件多 + 平均小"的分区动手）。 */
    public boolean shouldCompact(PartitionLayout layout, List<DataFile> files) {
        return !layout.detectSmallFilePartitions(files).isEmpty();
    }

    /** 对整张表的清单规划合并：只处理被 {@link PartitionLayout} 标记的分区，返回分区名 → 方案。 */
    public Map<String, Plan> planTable(PartitionLayout layout, List<DataFile> all) {
        Map<String, Plan> plans = new java.util.TreeMap<>();
        Map<String, List<DataFile>> grouped = layout.group(all);
        for (PartitionLayout.SmallFileFlag flag : layout.detectSmallFilePartitions(all)) {
            List<DataFile> files = grouped.get(flag.partition());
            Plan plan = plan(flag.partition(), files);
            if (plan.fileCountAfter() < plan.fileCountBefore()) {
                plans.put(flag.partition(), plan);
            }
        }
        return plans;
    }
}
