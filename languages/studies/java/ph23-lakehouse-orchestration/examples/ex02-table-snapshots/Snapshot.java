// languages/java/ph23-lakehouse-orchestration/examples/ex02-table-snapshots/Snapshot.java —— 不可变快照：表在某个时刻的完整定义
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex02 *.java && java -cp /tmp/ph23-ex02 TableSnapshotsDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：8/8 PASS）
//
// 为什么快照必须不可变：时间旅行的前提是「旧快照还在、且内容永远不变」。如果 filesByPartition 是可变的
// 引用，后续写入偷偷改了它，历史就会跟着变——「上周的数怎么变了」将永远查不出来。所以构造时做
// Map.copyOf 拷贝：快照一旦提交就冻结，读旧数据不需要副本。
import java.util.Map;
import java.util.Objects;

/**
 * 表的一个不可变快照。
 *
 * @param snapshotId        快照号：元数据层的单调序列（不是时间戳，不受时区/补数/乱序写入污染）
 * @param parentId          父快照号，构成单链；起点用 {@link #NO_PARENT}
 * @param tsMillis          提交时刻（毫秒），时间旅行按它回溯
 * @param operation         本次提交的操作语义（APPEND/COMPACT/...），用于排查「谁改的」
 * @param filesByPartition  分区 -> 该分区的文件数（示例用文件数代表清单；这是「当前状态」的全部内容）
 */
public record Snapshot(long snapshotId, long parentId, long tsMillis, String operation,
                       Map<String, Integer> filesByPartition) {

    /** 没有父快照（表的起点）。用显式常量而不是 0，避免和真实的 snapshotId=0 混淆。 */
    public static final long NO_PARENT = -1L;

    public Snapshot {
        Objects.requireNonNull(operation, "operation");
        Objects.requireNonNull(filesByPartition, "filesByPartition");
        // 冻结快照内容：提交之后任何人都不能改写它，否则时间旅行会读到被污染的历史
        filesByPartition = Map.copyOf(filesByPartition);
    }

    /** 全表文件数：把「清单」汇总成一个可比较的数字。 */
    public long totalFiles() {
        return filesByPartition.values().stream().mapToLong(Integer::longValue).sum();
    }
}
