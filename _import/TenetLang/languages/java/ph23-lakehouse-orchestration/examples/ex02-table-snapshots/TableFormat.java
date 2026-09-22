// languages/java/ph23-lakehouse-orchestration/examples/ex02-table-snapshots/TableFormat.java —— 表格式：CAS 原子提交 + 时间旅行 + 增量读 + schema 演进
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex02 *.java && java -cp /tmp/ph23-ex02 TableSnapshotsDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：8/8 PASS）
//
// 为什么用 AtomicReference + CAS：对象存储只有「整对象 PUT」一种原子操作，没有目录级事务，所以
// 「当前是哪个快照」必须收敛到**唯一一处可变指针**。CAS 成功 = 提交成功；CAS 失败说明别人先提交了，
// 重读 current 后再造新快照重试。这样任何时刻都不会出现「两份当前快照」，失败的重跑也污染不了表。
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

public final class TableFormat {

    /** 当前快照指针：整个表格式里唯一「可变」的位置。 */
    private final AtomicReference<Snapshot> currentRef;

    /** 快照号 -> 快照。CAS 成功后登记；因为只有提交成功的快照才会进来，历史里不会有孤儿。 */
    private final Map<Long, Snapshot> history = new ConcurrentHashMap<>();

    /** 列清单（schema），仅 ADD COLUMN 可以演进。 */
    private final List<String> columns = new CopyOnWriteArrayList<>();

    private final AtomicInteger commitCount = new AtomicInteger();
    private final AtomicInteger casRetries = new AtomicInteger();

    public TableFormat() {
        Snapshot genesis = new Snapshot(0L, Snapshot.NO_PARENT, 0L, "CREATE", Map.of());
        this.currentRef = new AtomicReference<>(genesis);
        this.history.put(0L, genesis);
        // 示例表的初始两列
        this.columns.add("instance_id");
        this.columns.add("event_ts");
    }

    public Snapshot current() {
        return currentRef.get();
    }

    public int commitCount() {
        return commitCount.get();
    }

    /** 版本冲突重试次数：只用于观测，不参与正确性判断（正确性由「无丢失提交」证明）。 */
    public int casRetries() {
        return casRetries.get();
    }

    public List<String> schema() {
        return List.copyOf(columns);
    }

    /** 从最新快照沿 parentId 回溯到起点，得到完整快照链（最新在前）。 */
    public List<Snapshot> chain() {
        List<Snapshot> out = new ArrayList<>();
        for (Snapshot s = currentRef.get(); s != null; s = history.get(s.parentId())) {
            out.add(s);
        }
        return List.copyOf(out);
    }

    /**
     * 原子提交一次写入，返回新快照。
     * 新的 snapshotId = 当前快照号 + 1，父指针指向当前快照；CAS 失败就重读重试。
     */
    public Snapshot commit(String operation, Map<String, Integer> filesByPartition, long nowMillis) {
        Objects.requireNonNull(operation, "operation");
        while (true) {
            Snapshot cur = currentRef.get();
            Snapshot next = new Snapshot(cur.snapshotId() + 1, cur.snapshotId(), nowMillis,
                    operation, filesByPartition);
            if (currentRef.compareAndSet(cur, next)) {
                // 先 CAS 再登记：历史里只会有「真的成为过 current」的快照，不会有未提交的孤儿
                history.put(next.snapshotId(), next);
                commitCount.incrementAndGet();
                return next;
            }
            casRetries.incrementAndGet();   // 版本冲突：别人抢先提交，重读 current 后重试
        }
    }

    /**
     * 时间旅行：沿快照链回溯到 tsMillis 之前（含）最近的一次快照。
     * 读旧数据不需要任何副本——这正是「清单 + 快照」相对「目录即表」的核心优势。
     */
    public Optional<Snapshot> timeTravel(long tsMillis) {
        Snapshot s = currentRef.get();
        while (s != null && s.tsMillis() > tsMillis) {
            s = history.get(s.parentId());
        }
        return Optional.ofNullable(s);
    }

    /**
     * 增量读：返回「自 sinceSnapshotId 以来 filesByPartition 有变化的分区」。
     * 用快照 id（元数据单调序列）而不是时间戳做基线：时间戳是数据内容的一部分，会被时区、补数、
     * 乱序写入污染；快照 id 是平台自己记账得出的确定答案。
     *
     * @return 变化分区 -> 当前文件数（分区在本快照消失时为 0）；按分区名排序，保证可复现
     */
    public Map<String, Integer> incremental(long sinceSnapshotId) {
        Snapshot baseline = ancestorAtOrBefore(sinceSnapshotId);
        if (baseline == null) {
            throw new IllegalArgumentException("未知快照: " + sinceSnapshotId);
        }
        Map<String, Integer> now = currentRef.get().filesByPartition();
        Set<String> partitions = new TreeSet<>(baseline.filesByPartition().keySet());
        partitions.addAll(now.keySet());

        Map<String, Integer> changed = new TreeMap<>();
        for (String p : partitions) {
            Integer before = baseline.filesByPartition().get(p);
            Integer after = now.get(p);
            if (!Objects.equals(before, after)) {
                changed.put(p, after == null ? 0 : after);
            }
        }
        return Map.copyOf(changed);
    }

    /**
     * schema 演进：ADD COLUMN 是安全的（旧数据该列为 null），放行；
     * DROP COLUMN / CHANGE TYPE 必须在**提交阶段** fail-fast，并说明「哪个列、为什么不兼容」——
     * 若静默通过，错误会推迟到下游任务运行时才炸，而那时坏数据可能已经写进 ADS。
     */
    public void evolveSchema(String change) {
        if (change == null || change.isBlank()) {
            throw new IllegalArgumentException("change 必填");
        }
        String c = change.trim();
        String upper = c.toUpperCase(Locale.ROOT);

        if (upper.startsWith("ADD COLUMN")) {
            String name = firstToken(c.substring("ADD COLUMN".length()));
            if (name.isEmpty()) {
                throw new IllegalArgumentException("ADD COLUMN 缺少列名: " + change);
            }
            if (!columns.contains(name)) {
                columns.add(name);
            }
            return;
        }
        if (upper.startsWith("DROP COLUMN")) {
            String name = firstToken(c.substring("DROP COLUMN".length()));
            throw new IllegalStateException("不兼容的 schema 变更被拒: DROP COLUMN " + name
                    + " —— 历史快照的数据文件仍按旧 schema 写入，删列后这些文件读不出来，下游也无法回退");
        }
        if (upper.startsWith("CHANGE TYPE")) {
            String rest = c.substring("CHANGE TYPE".length()).trim();
            throw new IllegalStateException("不兼容的 schema 变更被拒: CHANGE TYPE " + rest
                    + " —— 类型变更会让历史文件的解码与下游类型断言同时失败，必须新建列并显式回填");
        }
        throw new IllegalArgumentException("无法识别的 schema 变更: " + change);
    }

    private Snapshot ancestorAtOrBefore(long id) {
        Snapshot s = currentRef.get();
        while (s != null && s.snapshotId() > id) {
            s = history.get(s.parentId());
        }
        return s;
    }

    private static String firstToken(String s) {
        String trimmed = s.trim();
        if (trimmed.isEmpty()) {
            return "";
        }
        return trimmed.split("\\s+")[0];
    }
}
