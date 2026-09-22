// project/src/lakeplat/TableFormat.java —— 表格式：快照链 + CAS 原子提交 + 时间旅行 + 增量读 + schema 演进
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

/**
 * 表格式（主文档 3.2 / 4.1）：用「快照 + 清单 + 原子指针替换」给表补上 ACID 语义。
 *
 * <p>四个能力各由一个方法体现，且都能被确定性内存模型验证：
 * <table border="1">
 *   <caption>能力与机制</caption>
 *   <tr><th>能力</th><th>方法</th><th>机制</th></tr>
 *   <tr><td>原子提交</td><td>{@link #commit}</td><td>快照指针 CAS（期望父 id 不匹配则拒绝，调用方可重读重试）</td></tr>
 *   <tr><td>时间旅行</td><td>{@link #timeTravel(long)}</td><td>沿 parentId 链回溯到 ts 之前最近的一次快照</td></tr>
 *   <tr><td>增量读</td><td>{@link #incremental(Snapshot, Snapshot)}</td><td>比较两个快照的清单差异 → 只返回变化分区</td></tr>
 *   <tr><td>schema 演进</td><td>{@link #commit}</td><td>提交阶段校验兼容性，不兼容直接拒绝</td></tr>
 * </table>
 *
 * <p><b>为什么增量读比「按时间戳过滤」可靠</b>：时间戳是数据内容的一部分，会被时区、补数、乱序写入污染；
 * 而快照 id 是元数据的单调序列——「自 snapshot 1001 以来变了什么」是平台自己记账得出的确定答案。
 */
public final class TableFormat {

    /** CAS 提交结果：成功时给出新快照；失败时给出可读原因与已尝试次数（调用方重读后重试）。 */
    public record CommitResult(boolean accepted, Snapshot snapshot, int attempts, String message) {
        public static CommitResult rejected(int attempts, String message) {
            return new CommitResult(false, null, attempts, message);
        }
    }

    private final TableRef table;
    private final String partitionKey;
    private final Map<Long, Snapshot> byId = new LinkedHashMap<>();
    private Snapshot current;
    private long nextSnapshotId = 1000L;
    private long commitAttempts;

    public TableFormat(TableRef table, Schema initialSchema, long createdTs, String partitionKey) {
        this.table = table;
        this.partitionKey = partitionKey;
        Map<String, List<DataFile>> empty = new TreeMap<>();
        Snapshot created = new Snapshot(nextSnapshotId++, Snapshot.NO_PARENT, createdTs, "CREATE", initialSchema, empty);
        byId.put(created.snapshotId(), created);
        this.current = created;
    }

    public TableRef table() {
        return table;
    }

    public String partitionKey() {
        return partitionKey;
    }

    /** 当前快照指针（唯一的「可变」位置）。 */
    public Snapshot current() {
        return current;
    }

    public Schema schema() {
        return current.schema();
    }

    public long commitAttempts() {
        return commitAttempts;
    }

    public Snapshot snapshot(long snapshotId) {
        Snapshot snapshot = byId.get(snapshotId);
        if (snapshot == null) {
            throw new IllegalStateException("快照不存在：" + snapshotId + "（表 " + table.table() + "）");
        }
        return snapshot;
    }

    public List<Snapshot> history() {
        return List.copyOf(byId.values());
    }

    /** 父链连续性的自检：每个快照的 parentId 都指向真实存在的快照（首快照除外）。 */
    public boolean lineageContinuous() {
        for (Snapshot snapshot : byId.values()) {
            if (snapshot.parentId() != Snapshot.NO_PARENT && !byId.containsKey(snapshot.parentId())) {
                return false;
            }
            if (snapshot == current) {
                continue;
            }
            Snapshot child = childOf(snapshot.snapshotId());
            if (child != null && child.parentId() != snapshot.snapshotId()) {
                return false;
            }
        }
        return true;
    }

    private Snapshot childOf(long snapshotId) {
        for (Snapshot snapshot : byId.values()) {
            if (snapshot.parentId() == snapshotId) {
                return snapshot;
            }
        }
        return null;
    }

    /**
     * CAS 原子提交（主文档 3.2）：只有当 {@code expectedParentId} 仍是当前快照时才成功。
     *
     * <p>这里用一个「乐观并发」的内存版本：调用方先读 current 得到期望父 id，再带着它提交。
     * 若期间有别的提交者推进了指针，本次提交被拒绝（表保持原快照，读者看不到半成品），
     * 调用方重读后重试——**不会出现「两份当前快照」**。
     *
     * @param expectedParentId 提交者观测到的父快照 id
     * @param tsMillis         逻辑提交时间（由调用方显式传入，不读系统时间）
     * @param operation        操作类型（APPEND / OVERWRITE / COMPACT）
     * @param newSchema        提交后的 schema；不兼容变更在此被拒
     * @param newManifest      提交后的完整清单（分区 → 文件列表）
     */
    public CommitResult commit(long expectedParentId, long tsMillis, String operation,
                               Schema newSchema, Map<String, List<DataFile>> newManifest) {
        commitAttempts++;
        if (expectedParentId != current.snapshotId()) {
            return CommitResult.rejected((int) commitAttempts,
                    "CAS 冲突：期望父快照 #" + expectedParentId + " 但当前已是 #" + current.snapshotId()
                            + "（乐观提交失败，表保持原快照，请重读后重试）");
        }
        SchemaEvolution.check(current.schema(), newSchema);
        long id = nextSnapshotId++;
        Snapshot next = new Snapshot(id, current.snapshotId(), tsMillis, operation, newSchema, newManifest);
        byId.put(id, next);
        current = next;                       // 原子指针替换：这一行之前快照已完整构造
        return new CommitResult(true, next, (int) commitAttempts, null);
    }

    /** 便捷提交：在读-改-写循环里重读 current 再提交（演示「重试成功」的路径）。 */
    public CommitResult commitWithRetry(long tsMillis, String operation, Schema newSchema,
                                        Map<String, List<DataFile>> newManifest) {
        for (int attempt = 0; attempt < 8; attempt++) {
            CommitResult result = commit(current.snapshotId(), tsMillis, operation, newSchema, newManifest);
            if (result.accepted()) {
                return result;
            }
        }
        throw new IllegalStateException("CAS 重试 8 次仍未提交成功：" + table.table());
    }

    /** 时间旅行（主文档 3.2）：沿父链回溯到 {@code ts} 之前最近的一次快照；读旧数据不需要副本。 */
    public Snapshot timeTravel(long tsMillis) {
        Snapshot best = null;
        for (Snapshot snapshot : currentChain()) {
            if (snapshot.tsMillis() <= tsMillis) {
                best = snapshot;
            }
        }
        if (best == null) {
            throw new IllegalStateException("时间旅行失败：表 " + table.table() + " 在 ts=" + tsMillis + " 之前没有快照");
        }
        return best;
    }

    /** 当前快照的父链（从最早到当前）。 */
    public List<Snapshot> currentChain() {
        List<Snapshot> reversed = new ArrayList<>();
        Snapshot cursor = current;
        while (cursor != null) {
            reversed.add(cursor);
            cursor = cursor.parentId() == Snapshot.NO_PARENT ? null : byId.get(cursor.parentId());
        }
        Collections.reverse(reversed);
        return List.copyOf(reversed);
    }

    /**
     * 增量读（主文档 3.2）：从 {@code base} 到 {@code target} 之间**清单发生过变化**的分区集合。
     *
     * <p>只处理变化分区，下游因此省掉扫描量与计算量；判定依据是快照元数据而不是数据里的时间戳。
     */
    public Set<String> incremental(Snapshot base, Snapshot target) {
        Map<String, Integer> before = base.filesByPartition();
        Map<String, Integer> after = target.filesByPartition();
        Set<String> changed = new TreeSet<>();
        Set<String> partitions = new TreeSet<>(before.keySet());
        partitions.addAll(after.keySet());
        for (String partition : partitions) {
            int b = before.getOrDefault(partition, 0);
            int a = after.getOrDefault(partition, 0);
            if (b != a || !samePartitionBytes(base, target, partition)) {
                changed.add(partition);
            }
        }
        return changed;
    }

    private boolean samePartitionBytes(Snapshot base, Snapshot target, String partition) {
        List<DataFile> left = base.manifest().getOrDefault(partition, List.of());
        List<DataFile> right = target.manifest().getOrDefault(partition, List.of());
        if (left.size() != right.size()) {
            return false;
        }
        for (int i = 0; i < left.size(); i++) {
            if (!left.get(i).path().equals(right.get(i).path())) {
                return false;
            }
        }
        return true;
    }

    // ---------- 分区布局视角（主文档 3.3） ----------

    /** 清单的扁平分区分组视图（分区字典序，可直接喂给 {@link PartitionLayout}）。 */
    public Map<String, List<DataFile>> partitions() {
        return current.manifest();
    }

    /** 分区裁剪：只取命中分区谓词的文件（分区值是 `键=值` 或裸值都接受）。 */
    public List<DataFile> scan(Set<String> partitionPredicate) {
        List<DataFile> hit = new ArrayList<>();
        current.manifest().forEach((partition, files) -> {
            if (partitionPredicate.contains(partition) || partitionPredicate.contains(value(partition))) {
                hit.addAll(files);
            }
        });
        return List.copyOf(hit);
    }

    /** 全表扫描：不裁剪，任何查询都全扫（对照基准）。 */
    public List<DataFile> scanAll() {
        return current.files();
    }

    /** 当前清单涉及的全部分区（`键=值`）。 */
    public Set<String> partitionValues() {
        return new TreeSet<>(current.manifest().keySet());
    }

    private static String value(String partition) {
        int eq = partition.indexOf('=');
        return eq < 0 ? partition : partition.substring(eq + 1);
    }

    /** 生成一个「把某分区整体替换成 {@code files}」的清单（分区整体覆盖，不追加）。 */
    public Map<String, List<DataFile>> withReplaced(String partition, List<DataFile> files) {
        Map<String, List<DataFile>> next = new LinkedHashMap<>(current.manifest());
        next.put(partition, List.copyOf(files));
        return next;
    }

    /** 生成一个「把某分区整体删掉」的清单（源里删掉的行要能真的消失）。 */
    public Map<String, List<DataFile>> withRemoved(String partition) {
        Map<String, List<DataFile>> next = new LinkedHashMap<>(current.manifest());
        next.remove(partition);
        return next;
    }

    /** 生成一个「新增分区」的清单。 */
    public Map<String, List<DataFile>> withAdded(String partition, List<DataFile> files) {
        Map<String, List<DataFile>> next = new LinkedHashMap<>(current.manifest());
        if (next.containsKey(partition)) {
            throw new IllegalStateException("分区已存在，追加请用分区整体覆盖：" + partition);
        }
        next.put(partition, List.copyOf(files));
        return next;
    }

    /** 生成文件路径：`data/<分区>/part-000N.parquet`（确定性，无随机、无时间戳）。 */
    public String filePath(String partition, int index) {
        return "data/" + table.table() + "/" + partition + "/part-" + String.format("%04d", index) + ".parquet";
    }

    /** 用「行数 + 每行字节」确定性造一个文件。 */
    public DataFile makeFile(String partition, int index, long rows, long bytesPerRow) {
        return new DataFile(filePath(partition, index), partition, rows, rows * bytesPerRow);
    }

    /** 集合视图：把 {@link LinkedHashSet} 收敛成确定性顺序的分区集合。 */
    public static Set<String> ordered(Set<String> partitions) {
        return Collections.unmodifiableSet(new LinkedHashSet<>(new TreeSet<>(partitions)));
    }

    @Override
    public String toString() {
        return table.table() + " current=" + current.label();
    }
}
