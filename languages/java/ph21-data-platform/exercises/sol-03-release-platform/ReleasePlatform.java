// exercises/sol-03-ota-platform/ReleasePlatform.java —— 版本发布升级平台(参考实现)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-sol *.java
//
// 题目要求(roadmap §21 练习「版本发布升级平台」)：
//   - 版本库：发布新版本，禁止版本倒退(只能发比当前最高更高的版本)；
//   - 批次管理：为一个已发布版本创建升级批次(绑定若干 SOURCE_ID)，可查询批次进度；
//   - 数据源级推进 + 审计：批次内每个g独立状态机，非法迁移被拒，所有迁移留审计；
//   - 并发安全：不同批次可在不同线程同时推进，互不干扰。
// 参考实现：平台层只管「版本库 + 批次注册表」，批次内部自带上锁状态机(ex06 的工程版组织)。
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public final class ReleasePlatform {
    /** 数据源级任务状态机(可加 ROLLED_BACK 表示整体回滚的落点)。 */
    public enum TaskState { PENDING, DOWNLOADING, INSTALLING, SUCCEEDED, FAILED, ROLLED_BACK }

    public record BatchSummary(int total, Map<TaskState, Long> byState) { }
    public record BatchInfo(String batchId, ReleaseVersion version, List<String> vins) { }

    private final List<ReleaseVersion> publishedVersions = new ArrayList<>();   // 只增不减
    private final ConcurrentHashMap<String, Batch> batches = new ConcurrentHashMap<>();

    /** 发布版本：必须严格高于当前最高版本(防止版本倒退把已升级g搞乱)。 */
    public synchronized ReleaseVersion publish(String version) {
        ReleaseVersion v = ReleaseVersion.of(version);
        ReleaseVersion highest = publishedVersions.isEmpty() ? null : publishedVersions.get(publishedVersions.size() - 1);
        if (highest != null && v.compareTo(highest) <= 0) {
            throw new IllegalArgumentException("版本倒退: " + version + " <= 最高 " + highest);
        }
        publishedVersions.add(v);
        return v;
    }

    public ReleaseVersion highestVersion() {
        return publishedVersions.isEmpty() ? null : publishedVersions.get(publishedVersions.size() - 1);
    }

    /** 创建批次：版本必须已发布；目标数据源非空。 */
    public Batch createBatch(String batchId, String version, List<String> vins) {
        ReleaseVersion target = publishedVersions.stream()
                .filter(v -> v.toString().equals(version)).findFirst()
                .orElseThrow(() -> new IllegalArgumentException("版本未发布: " + version));
        Batch b = new Batch(batchId, target, List.copyOf(vins));
        if (batches.putIfAbsent(batchId, b) != null) {
            throw new IllegalArgumentException("批次已存在: " + batchId);
        }
        return b;
    }

    public Batch batch(String batchId)  { return batches.get(batchId); }
    public List<String> batchIds()      { return batches.keySet().stream().sorted().toList(); }
    public List<ReleaseVersion> published() { return List.copyOf(publishedVersions); }

    /** 一个批次 = 数据源级状态机 + 审计。advance 用 synchronized 串行化(批内g少，锁开销可忽略)。 */
    public static final class Batch {
        private final String batchId;
        private final ReleaseVersion version;
        private final ConcurrentHashMap<String, TaskState> perVin = new ConcurrentHashMap<>();
        private final List<String> audit = new ArrayList<>();

        Batch(String batchId, ReleaseVersion version, List<String> vins) {
            this.batchId = batchId;
            this.version = version;
            vins.forEach(v -> perVin.put(v, TaskState.PENDING));
        }

        public String batchId()  { return batchId; }
        public ReleaseVersion version() { return version; }

        /** 期望当前状态 = from，迁移到 to；否则抛异常(防并发重复推进)。 */
        public synchronized void advance(String sourceId, TaskState from, TaskState to) {
            TaskState cur = perVin.get(sourceId);
            if (cur == null) {
                throw new IllegalArgumentException("批次不含数据源: " + sourceId);
            }
            if (cur != from) {
                throw new IllegalStateException("数据源 " + sourceId + " 期望 " + from + " 实际 " + cur);
            }
            perVin.put(sourceId, to);
            audit.add(String.format("%s %s->%s batch=%s", sourceId, from, to, batchId));
        }

        public synchronized TaskState stateOf(String sourceId) { return perVin.get(sourceId); }

        public BatchSummary summary() {
            Map<TaskState, Long> byState = new EnumMap<>(TaskState.class);
            perVin.values().forEach(s -> byState.merge(s, 1L, Long::sum));
            return new BatchSummary(perVin.size(), byState);
        }

        public List<String> auditLog() { return List.copyOf(audit); }
    }
}
