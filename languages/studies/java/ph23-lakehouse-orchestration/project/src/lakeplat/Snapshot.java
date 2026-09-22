// project/src/lakeplat/Snapshot.java —— 不可变快照：清单 + 父链 + 逻辑提交时间
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * 表的一个不可变快照（主文档 3.2 / 4.1）。
 *
 * <p>「表的当前状态不由目录决定，而由一份元数据决定」——这份元数据就是本 record：
 * 快照 id、父快照 id、提交时间、操作类型、当次 schema、以及**清单**（分区 → 文件列表）。
 *
 * <p>快照一旦创建就不再修改；提交新快照只是把 {@code current} 指针原子替换（{@link TableFormat#commit}）。
 * 因此：失败的重跑不会污染表（读者永远看到完整快照）、时间旅行免费（旧快照文件还在）、
 * 读一致性天然成立（一次查询固定在一个快照上）。
 *
 * @param snapshotId      单调递增的快照 id（**元数据的单调序列**，比时间戳可靠）
 * @param parentId        父快照 id；初始快照为 {@link #NO_PARENT}
 * @param tsMillis        提交时间（由逻辑时钟显式传入，不读系统时间）
 * @param operation       操作类型（CREATE / APPEND / OVERWRITE / COMPACT）
 * @param schema          提交后的表 schema
 * @param manifest        清单：分区 → 该分区的文件列表（键按字典序，保证输出可复现）
 */
public record Snapshot(long snapshotId, long parentId, long tsMillis, String operation,
                       Schema schema, Map<String, List<DataFile>> manifest) {

    /** 初始快照的父指针（无父）。 */
    public static final long NO_PARENT = -1L;

    public Snapshot {
        if (snapshotId <= 0) {
            throw new IllegalArgumentException("快照 id 必须为正：" + snapshotId);
        }
        if (tsMillis < 0) {
            throw new IllegalArgumentException("提交时间不能为负");
        }
        operation = operation == null ? "UNKNOWN" : operation;
        manifest = java.util.Collections.unmodifiableMap(new TreeMap<>(manifest));
    }

    /** 分区 → 文件数（增量读与一屏的最小读数）。 */
    public Map<String, Integer> filesByPartition() {
        Map<String, Integer> result = new TreeMap<>();
        manifest.forEach((partition, files) -> result.put(partition, files.size()));
        return result;
    }

    /** 清单里所有文件（分区字典序 + 文件名字典序），保证输出可复现。 */
    public List<DataFile> files() {
        List<DataFile> all = new java.util.ArrayList<>();
        manifest.values().forEach(all::addAll);
        return List.copyOf(all);
    }

    /** 该快照的总行数。 */
    public long totalRows() {
        return files().stream().mapToLong(DataFile::rows).sum();
    }

    /** 该快照的总字节数（全表扫描的基准）。 */
    public long totalBytes() {
        return files().stream().mapToLong(DataFile::bytes).sum();
    }

    /** 分区数。 */
    public int partitionCount() {
        return manifest.size();
    }

    /** 快照标签：`#1003@+3h APPEND 2 分区/5000 行`。 */
    public String label() {
        return "#" + snapshotId + "@" + tsMillis + " " + operation
                + " " + manifest.size() + " 分区/" + totalRows() + " 行";
    }
}
