// project/src/dataplat/ReleasePlatform.java —— 版本发布平台：版本库 + 批次编排 + 单节点状态机 + 审计
package dataplat;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/dataplat/*.java
//
// 三个职责：
//   1. 版本库：只能发布比当前最高更高的版本(禁版本倒退)；
//   2. 批次：一个批次 = 目标版本 + 一组 SOURCE_ID；批内每个数据源一个状态机，advance 校验期望状态；
//   3. 审计：平台与批次的操作全部留审计作业历史(合规要求，无法删除)。
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

public final class ReleasePlatform {
    public enum TaskState { PENDING, DOWNLOADING, INSTALLING, SUCCEEDED, FAILED, ROLLED_BACK }
    public record AuditLine(String detail) { }

    private final List<ReleaseVersion> versions = new ArrayList<>();
    private final ConcurrentHashMap<String, ReleaseBatch> batches = new ConcurrentHashMap<>();
    private final List<AuditLine> platformAudit = new ArrayList<>();

    public synchronized ReleaseVersion publish(String v) {
        ReleaseVersion next = ReleaseVersion.of(v);
        ReleaseVersion highest = versions.isEmpty() ? null : versions.get(versions.size() - 1);
        if (highest != null && next.compareTo(highest) <= 0) {
            throw new IllegalArgumentException("禁止版本倒退: " + v + " <= " + highest);
        }
        versions.add(next);
        platformAudit.add(new AuditLine("publish " + v));
        return next;
    }

    public ReleaseVersion highest() { return versions.isEmpty() ? null : versions.get(versions.size() - 1); }

    public ReleaseBatch createBatch(String batchId, String version, List<String> vins) {
        if (!versions.contains(ReleaseVersion.of(version))) {
            throw new IllegalArgumentException("版本未发布: " + version);
        }
        ReleaseBatch batch = new ReleaseBatch(batchId, ReleaseVersion.of(version), vins, this);
        if (batches.putIfAbsent(batchId, batch) != null) {
            throw new IllegalArgumentException("批次已存在: " + batchId);
        }
        platformAudit.add(new AuditLine("createBatch " + batchId + " -> " + version + " vins=" + vins.size()));
        return batch;
    }

    public ReleaseBatch batch(String id) { return batches.get(id); }
    public List<ReleaseBatch> allBatches() {
        return batches.values().stream().sorted((a, b) -> a.id().compareTo(b.id())).toList();
    }
    public int batchCount()         { return batches.size(); }
    public List<AuditLine> audit()  { return List.copyOf(platformAudit); }
    void auditPlatform(String detail) { platformAudit.add(new AuditLine(detail)); }

    /** 一个批次：串行推进 + 审计(线程安全见 advance 的 synchronized)。 */
    public static final class ReleaseBatch {
        private final String id;
        private final ReleaseVersion target;
        private final ConcurrentHashMap<String, TaskState> perVin = new ConcurrentHashMap<>();
        private final List<String> audit = new ArrayList<>();
        private final ReleasePlatform platform;

        ReleaseBatch(String id, ReleaseVersion target, List<String> vins, ReleasePlatform platform) {
            this.id = id;
            this.target = target;
            this.platform = platform;
            vins.forEach(v -> perVin.put(v, TaskState.PENDING));
        }

        public synchronized void advance(String sourceId, TaskState from, TaskState to) {
            TaskState cur = perVin.get(sourceId);
            if (cur == null) {
                throw new IllegalArgumentException("批次不含数据源 " + sourceId);
            }
            if (cur != from) {
                throw new IllegalStateException("数据源 " + sourceId + " 期望 " + from + " 实际 " + cur);
            }
            perVin.put(sourceId, to);
            audit.add(sourceId + " " + from + "->" + to);
            platform.auditPlatform("batch " + id + " " + sourceId + " " + from + "->" + to);
        }

        public synchronized void rollback(String sourceId) {
            advance(sourceId, TaskState.FAILED, TaskState.ROLLED_BACK);
        }

        public TaskState stateOf(String sourceId) { return perVin.get(sourceId); }
        public long count(TaskState s) { return perVin.values().stream().filter(t -> t == s).count(); }
        public int vehicleCount()      { return perVin.size(); }
        public List<String> audit()    { return List.copyOf(audit); }
        public String id()             { return id; }
        public ReleaseVersion target()     { return target; }
    }
}
