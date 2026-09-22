// languages/java/ph23-lakehouse-orchestration/examples/ex04-compaction/Compaction.java —— 小文件合并：决策判据 + 收益测算 + 幂等重写
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex04 *.java && java -cp /tmp/ph23-ex04 CompactionDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
//
// 口径说明（readSavedRatio 到底在度量什么）：
//   合并**不改变数据字节数**（bytesAfter = bytesBefore，只是把 n 个小文件重写成 m 个大文件，不做压缩）。
//   读取代价的模型是 4.2 节的两项：readCost = Σbytes + 每次打开文件的固定开销 × 文件数。
//   收益来自第二项：文件数从 n 降到 m，打开/列元数据的开销按比例下降。因此
//     readSavedRatio = (readCostBefore - readCostAfter) / readCostBefore
//   OPEN_COST_BYTES_PER_FILE 是「打开一个文件相当于多读多少字节」的建模常量（示例取 4KB），
//   它不是真实引擎的常量，而是把「打开文件数」换算成可比字节的**度量口径**——数字本身可调，口径必须写清。
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public final class Compaction {

    /** 打开一个文件的固定代价折算成字节（元数据 + IO 摊销）。口径常量，可调但必须写明。 */
    public static final long OPEN_COST_BYTES_PER_FILE = 4_096L;

    /**
     * 一次合并方案。
     *
     * @param partition       目标分区
     * @param fileCountBefore 合并前文件数
     * @param fileCountAfter  合并后文件数
     * @param bytesBefore     合并前总字节
     * @param bytesAfter      合并后总字节（= bytesBefore：合并只重排，不压缩）
     * @param readSavedRatio  按 readCost 口径算出的读取代价下降比例；无需合并时为 0
     */
    public record Plan(String partition, int fileCountBefore, int fileCountAfter,
                       long bytesBefore, long bytesAfter, double readSavedRatio) {

        /** 空方案：文件数 <= minFiles 或平均大小已达标，合并无收益。 */
        public boolean isNoop() {
            return fileCountAfter >= fileCountBefore && bytesAfter == bytesBefore;
        }

        static Plan noop(String partition, int files, long bytes) {
            return new Plan(partition, files, files, bytes, bytes, 0.0);
        }
    }

    private Compaction() {
    }

    /**
     * 产出合并方案：分区内文件数 > minFiles 且平均文件大小 < targetBytes 时，合并到接近 targetBytes。
     *
     * @param files       候选文件（可以包含其他分区，只有 partition 命中的参与计算）
     * @param targetBytes 目标文件大小
     * @param minFiles    文件数阈值：不超过它就不值得起一次重写
     */
    public static Plan plan(String partition, List<DataFile> files, long targetBytes, int minFiles) {
        if (partition == null || partition.isBlank()) {
            throw new IllegalArgumentException("partition 必填");
        }
        if (targetBytes <= 0) {
            throw new IllegalArgumentException("targetBytes 必须为正: " + targetBytes);
        }
        if (minFiles < 0) {
            throw new IllegalArgumentException("minFiles 不能为负: " + minFiles);
        }

        List<DataFile> in = files.stream().filter(f -> f.partition().equals(partition)).toList();
        int n = in.size();
        long bytesBefore = in.stream().mapToLong(DataFile::bytes).sum();
        if (n == 0) {
            return Plan.noop(partition, 0, 0L);
        }
        long avg = bytesBefore / n;
        // 判据：文件多「且」平均小。文件多但每个都大 → 正常分片；文件少且小 → 小表，都不该合并。
        if (n <= minFiles || avg >= targetBytes) {
            return Plan.noop(partition, n, bytesBefore);
        }

        int after = (int) Math.max(1L, (bytesBefore + targetBytes - 1) / targetBytes);
        long readBefore = readCost(bytesBefore, n);
        long readAfter = readCost(bytesBefore, after);
        double saved = (readBefore - readAfter) / (double) readBefore;
        return new Plan(partition, n, after, bytesBefore, bytesBefore, saved);
    }

    /**
     * 执行合并：把分区内的文件重写成 fileCountAfter 个大小尽量均匀的文件，字节与行数总量不变。
     * 幂等：apply 只依赖 (files, plan)，同样输入必然得到同样输出；对已合并结果重新 plan 得到空方案，
     * apply 会原样返回——所以「跑两遍 compaction」不会把数据越合越乱（与 3.7 的幂等写同一条纪律）。
     */
    public static List<DataFile> apply(List<DataFile> files, Plan plan) {
        List<DataFile> in = files.stream()
                .filter(f -> f.partition().equals(plan.partition()))
                .sorted(Comparator.comparing(DataFile::path))
                .toList();

        // 空方案，或输入与方案不匹配（文件数对不上）→ 原样返回，不做任何猜测性重写
        if (plan.isNoop() || in.size() != plan.fileCountBefore()) {
            return List.copyOf(in);
        }

        long rowsBefore = in.stream().mapToLong(DataFile::rows).sum();
        int m = plan.fileCountAfter();
        long baseBytes = plan.bytesAfter() / m;
        long remBytes = plan.bytesAfter() % m;
        long baseRows = rowsBefore / m;
        long remRows = rowsBefore % m;

        List<DataFile> out = new ArrayList<>(m);
        for (int i = 0; i < m; i++) {
            long b = baseBytes + (i < remBytes ? 1L : 0L);
            long r = baseRows + (i < remRows ? 1L : 0L);
            out.add(new DataFile(String.format("%s/compact-%03d.parquet", plan.partition(), i + 1),
                    plan.partition(), r, b));
        }
        return List.copyOf(out);
    }

    /** 读取代价口径：扫描字节 + 打开文件数 × 单文件固定开销。 */
    public static long readCost(long bytes, int fileCount) {
        return bytes + OPEN_COST_BYTES_PER_FILE * fileCount;
    }
}
