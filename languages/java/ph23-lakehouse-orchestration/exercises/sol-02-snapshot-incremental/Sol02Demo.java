// exercises/sol-02-snapshot-incremental/Sol02Demo.java —— 练习 2 验收入口：快照链 + CAS 提交 + 时间旅行 + 增量读 + 受影响分区
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-sol02 *.java && java -cp /tmp/ph23-sol02 Sol02Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：12/12 PASS）

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

/**
 * 对应 23-lakehouse-orchestration.md 3.2（ACID 表与快照）、4.1 与第 7 章练习 2（sol-02）。
 * 断言围绕四条纪律：① 快照链 parent 连续（提交 = 原子替换指针）；② 时间旅行按链回溯；
 * ③ 增量读只含变化分区且边界为空；④ CAS 并发提交只有一个成功、失败者乐观重试。
 */
public final class Sol02Demo {

    private static int passed = 0;
    private static int total = 0;

    public static void main(String[] args) {
        TableFormat table = new TableFormat();

        Snapshot s1 = table.commit(new LinkedHashMap<>(
                Map.of("dt=2024-06-01", 2, "dt=2024-06-02", 1)), 1_718_000_000_000L, "append");
        Snapshot s2 = table.commit(new LinkedHashMap<>(
                Map.of("dt=2024-06-02", 2, "dt=2024-06-03", 1)), 1_718_000_100_000L, "append");
        Snapshot s3 = table.commit(new LinkedHashMap<>(
                Map.of("dt=2024-06-03", 3, "dt=2024-06-04", 1)), 1_718_000_200_000L, "overwrite");

        // ---- 1) 快照链 parent 连续 + id 单调 ----
        Snapshot c1 = table.snapshot(s1.snapshotId()).orElseThrow();
        Snapshot c2 = table.snapshot(s2.snapshotId()).orElseThrow();
        Snapshot c3 = table.snapshot(s3.snapshotId()).orElseThrow();
        check(c1.parentId() == -1L && c2.parentId() == c1.snapshotId() && c3.parentId() == c2.snapshotId(),
                "快照链 parent 连续：s1(-1) → s2(" + c1.snapshotId() + ") → s3(" + c2.snapshotId() + ")");

        check(c1.snapshotId() < c2.snapshotId() && c2.snapshotId() < c3.snapshotId()
                        && s1.snapshotId() == 1L && s2.snapshotId() == 2L && s3.snapshotId() == 3L,
                "快照 id 单调递增：1 < 2 < 3（元数据单调序列，比时间戳可靠）");

        // ---- 2) 时间旅行命中正确快照 ----
        Snapshot travel = table.timeTravel(1_718_000_150_000L);
        check(travel.snapshotId() == s2.snapshotId()
                        && travel.filesByPartition().equals(s2.filesByPartition()),
                "时间旅行命中正确快照：ts 落在 s2 与 s3 之间 → 回溯到 s2（含其分区布局）");

        Snapshot beforeAll = table.timeTravel(1_000_000_000_000L);
        Snapshot afterAll = table.timeTravel(9_999_999_999_999L);
        check(beforeAll.snapshotId() == s1.snapshotId()
                        && afterAll.snapshotId() == s3.snapshotId()
                        && beforeAll.tsMillis() == s1.tsMillis(),
                "时间旅行边界：早于全部快照 → 最早快照；晚于全部快照 → 当前快照");

        // ---- 3) 增量读只含变化分区，边界（since 等于当前快照）= 空 ----
        Incremental incremental = table.incremental(s1.snapshotId());
        check(incremental.changedPartitions().equals(Set.of("dt=2024-06-01", "dt=2024-06-02",
                        "dt=2024-06-03", "dt=2024-06-04"))
                        && incremental.addedPartitions().equals(Set.of("dt=2024-06-03", "dt=2024-06-04"))
                        && incremental.removedPartitions().equals(Set.of("dt=2024-06-01", "dt=2024-06-02"))
                        && incremental.fromId() == s1.snapshotId()
                        && incremental.toId() == s3.snapshotId(),
                "增量读只含变化分区：since s1 → changed {06-01,06-02,06-03,06-04}，"
                        + "新增 {06-03,06-04}，删除 {06-01,06-02}");

        Incremental empty = table.incremental(s3.snapshotId());
        check(empty.isEmpty() && empty.changedPartitions().isEmpty(),
                "增量读边界：since 等于当前快照 → 空增量（不需要重算任何分区）");

        Map<String, Integer> partitionDiff = table.partitionDiff(s2.snapshotId(), s3.snapshotId());
        check(partitionDiff.equals(Map.of("dt=2024-06-02", -2, "dt=2024-06-03", 2, "dt=2024-06-04", 1)),
                "分区差异可比：s2 → s3 的变化量 {06-02:-2, 06-03:+2, 06-04:+1}");

        // ---- 4) 按快照差异重算受影响分区 ----
        List<String> affected = table.affectedPartitions(s1.snapshotId(), s3.snapshotId());
        check(affected.equals(List.of("dt=2024-06-01", "dt=2024-06-02", "dt=2024-06-03", "dt=2024-06-04"))
                        && table.affectedPartitions(s3.snapshotId(), s3.snapshotId()).isEmpty(),
                "受影响分区列表确定且有序：s1→s3 = [06-01,06-02,06-03,06-04]，同快照为空");

        // ---- 5) CAS 并发提交只有一个成功（两个线程 + 乐观重试）----
        TableFormat concurrent = new TableFormat();
        Snapshot base = concurrent.commit(new LinkedHashMap<>(Map.of("dt=2024-06-01", 1)),
                1_718_100_000_000L, "append");

        AtomicReference<Snapshot> shared = new AtomicReference<>(base);
        CountDownLatch start = new CountDownLatch(1);
        List<CommitAttempt> attempts = Collections.synchronizedList(new ArrayList<>());

        Thread a = committer(shared, attempts, start,
                new LinkedHashMap<>(Map.of("dt=2024-06-01", 10)), 1_718_100_100_000L, "writer-A");
        Thread b = committer(shared, attempts, start,
                new LinkedHashMap<>(Map.of("dt=2024-06-02", 1)), 1_718_100_200_000L, "writer-B");
        start.countDown();
        join(a, b);

        List<CommitAttempt> ordered = attempts.stream()
                .sorted(Comparator.comparingLong(CommitAttempt::commitId))
                .toList();
        Snapshot head = shared.get();
        long winnerCount = ordered.stream().filter(CommitAttempt::wonFromBase).count();
        long rejectedCount = ordered.stream().filter(attempt -> !attempt.wonFromBase()).count();
        long landedCount = ordered.stream().filter(CommitAttempt::committed).count();
        // 每条提交的 base 要么是最初的 base，要么是列表中更早的一条提交——链不断。
        boolean everyBaseIsEarlierCommit = ordered.stream()
                .allMatch(attempt -> attempt.baseId() == base.snapshotId()
                        || ordered.stream()
                                .anyMatch(other -> other.commitId() == attempt.baseId()
                                        && other.commitId() < attempt.commitId()));
        check(winnerCount == 1 && rejectedCount == 1 && landedCount == 2
                        && ordered.size() == 2
                        && ordered.get(0).commitId() == base.snapshotId() + 1L
                        && ordered.get(1).commitId() == base.snapshotId() + 2L
                        && ordered.get(1).baseId() == ordered.get(0).commitId()
                        && head.snapshotId() == ordered.get(1).commitId()
                        && everyBaseIsEarlierCommit,
                "CAS 并发提交：争抢同一 base 只有一个写者成功（" + rejectedCount
                        + " 个被拒后重读重试），两条提交串成链 s" + base.snapshotId() + " → s"
                        + ordered.get(0).commitId() + " → s" + ordered.get(1).commitId()
                        + "（无「两份当前快照」）");

        check(winnerCount == 1 && rejectedCount == 1 && landedCount == 2
                        && head.parentId() < head.snapshotId()
                        && head.parentId() >= base.snapshotId(),
                "CAS 失败者可观测：1 次 compareAndSet 失败触发乐观重试，两个写者最终都落地且 id 单调");

        // ---- 6) 提交安全性：重放同一覆盖操作，分区布局不变、差异为空 ----
        TableFormat replay = new TableFormat();
        Snapshot r1 = replay.commit(new LinkedHashMap<>(Map.of("dt=2024-07-01", 1)),
                1_718_200_000_000L, "append");
        Snapshot r2 = replay.commit(new LinkedHashMap<>(Map.of("dt=2024-07-01", 3)),
                1_718_200_100_000L, "overwrite");
        Snapshot again = replay.commit(new LinkedHashMap<>(Map.of("dt=2024-07-01", 3)),
                1_718_200_200_000L, "overwrite");
        check(r1.snapshotId() < r2.snapshotId() && r2.snapshotId() < again.snapshotId()
                        && replay.current().snapshotId() == again.snapshotId()
                        && replay.current().filesByPartition().equals(Map.of("dt=2024-07-01", 3))
                        && replay.affectedPartitions(r2.snapshotId(), again.snapshotId()).isEmpty(),
                "重放同一覆盖操作：当前分区布局不变、与上一快照的分区差异为空（回填幂等的表格式前提）");

        boolean staleRejected = !replay.commit(r1, Map.of("dt=2024-07-02", 1), 1_718_200_300_000L,
                "stale-write");
        check(staleRejected && replay.current().snapshotId() == again.snapshotId(),
                "过期 base 的 CAS 提交被拒：写者必须重读当前快照后重试，指针不动");

        System.out.println("快照链: " + table.chainText());
        System.out.println("时间旅行: ts=1718000150000 → snapshot " + travel.snapshotId());
        System.out.println("增量读: " + incremental);
        System.out.println("ALL PASS: " + passed + "/" + total);
        if (passed != total) {
            System.exit(1);
        }
    }

    /**
     * 一个写者线程：读当前快照 → 拿自己读到的 base 去 CAS → 失败就重读当前指针再试。
     * 每个写者恰好汇报一条结果，于是「争抢同一 base 只有一个成功、失败者重试后落地」
     * 这件事不依赖线程调度，可以直接断言（见 CommitAttempt）。
     */
    private static Thread committer(AtomicReference<Snapshot> shared, List<CommitAttempt> attempts,
                                    CountDownLatch start, Map<String, Integer> files, long ts,
                                    String operation) {
        Thread thread = new Thread(() -> {
            await(start);
            Snapshot cursor = shared.get();
            long baseId = cursor.snapshotId();
            boolean classified = false;
            boolean won = false;
            for (int hop = 0; hop < 100; hop++) {
                Snapshot next = new Snapshot(cursor.snapshotId() + 1, cursor.snapshotId(), ts, operation,
                        new LinkedHashMap<>(files));
                if (shared.compareAndSet(cursor, next)) {
                    attempts.add(new CommitAttempt(operation, next.snapshotId(), next.parentId(), won));
                    return;
                }
                if (!classified) {
                    Snapshot now = shared.get();
                    won = now.snapshotId() != baseId || now.parentId() != cursor.parentId();
                    classified = true;
                    cursor = now;
                } else {
                    cursor = shared.get();
                }
            }
            throw new IllegalStateException("乐观重试超过上限：" + operation);
        }, operation);
        thread.start();
        return thread;
    }

    private static void join(Thread a, Thread b) {
        try {
            a.join();
            b.join();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("等待提交线程被中断", e);
        }
    }

    private static void await(CountDownLatch latch) {
        try {
            latch.await();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("等待起跑信号被中断", e);
        }
    }

    /**
     * 表格式：当前状态由「当前快照指针」决定，而不是目录内容。
     * 每次写入产生一个新快照（parent 指向提交时的当前快照），提交 = 原子替换指针。
     */
    public static final class TableFormat {

        private final AtomicReference<Snapshot> current = new AtomicReference<>();
        private final List<Snapshot> committed = new ArrayList<>();
        private final AtomicLong nextId = new AtomicLong(1L);

        /** 提交一个新快照：以当前快照为 parent，成功即原子替换指针。 */
        public synchronized Snapshot commit(Map<String, Integer> filesByPartition, long tsMillis,
                                            String operation) {
            Snapshot parent = current.get();
            long parentId = parent == null ? -1L : parent.snapshotId();
            Snapshot snapshot = new Snapshot(nextId.getAndIncrement(), parentId, tsMillis, operation,
                    new LinkedHashMap<>(filesByPartition));
            committed.add(snapshot);
            current.set(snapshot);
            return snapshot;
        }

        /**
         * CAS 提交：仅当当前指针仍是 {@code expected} 时替换。
         * false 意味着「有人先提交了」——调用者必须重读后决定重试还是放弃（不能盲写）。
         */
        public boolean commit(Snapshot expected, Map<String, Integer> filesByPartition, long tsMillis,
                              String operation) {
            Snapshot next = new Snapshot(expected.snapshotId() + 1, expected.snapshotId(), tsMillis,
                    operation, new LinkedHashMap<>(filesByPartition));
            if (current.compareAndSet(expected, next)) {
                synchronized (this) {
                    committed.add(next);
                }
                return true;
            }
            return false;
        }

        public Snapshot current() {
            Snapshot snapshot = current.get();
            if (snapshot == null) {
                throw new IllegalStateException("表上还没有任何快照");
            }
            return snapshot;
        }

        public java.util.Optional<Snapshot> snapshot(long snapshotId) {
            for (Snapshot snapshot : committed) {
                if (snapshot.snapshotId() == snapshotId) {
                    return java.util.Optional.of(snapshot);
                }
            }
            return java.util.Optional.empty();
        }

        public List<Snapshot> history() {
            return List.copyOf(committed);
        }

        /**
         * 时间旅行：沿 parent 链回溯到「ts 之前最近的一次提交」。
         * 早于全部快照时给出最早快照（没有更早的历史可读）。
         */
        public Snapshot timeTravel(long tsMillis) {
            Snapshot head = current.get();
            if (head == null) {
                throw new IllegalStateException("表上还没有任何快照");
            }
            if (head.tsMillis() <= tsMillis) {
                return head;
            }
            Snapshot cursor = head;
            while (cursor.parentId() != -1L) {
                long parentId = cursor.parentId();
                Snapshot parent = snapshot(parentId).orElseThrow(
                        () -> new IllegalStateException("快照链断裂：找不到 parent " + parentId));
                if (parent.tsMillis() <= tsMillis) {
                    return parent;
                }
                cursor = parent;
            }
            return cursor;
        }

        /** 增量读：自 {@code sinceId} 以来新增/变更的分区（不含删除）。 */
        public Incremental incremental(long sinceId) {
            Snapshot from = snapshot(sinceId).orElseThrow(
                    () -> new IllegalStateException("未知快照 id：" + sinceId));
            Snapshot to = current.get();
            LinkedHashSet<String> added = new LinkedHashSet<>();
            TreeSet<String> changed = new TreeSet<>();
            LinkedHashSet<String> removed = new LinkedHashSet<>();

            Set<String> all = new TreeSet<>(from.filesByPartition().keySet());
            all.addAll(to.filesByPartition().keySet());
            for (String partition : all) {
                int was = from.filesByPartition().getOrDefault(partition, 0);
                int now = to.filesByPartition().getOrDefault(partition, 0);
                if (was == now) {
                    continue;
                }
                changed.add(partition);
                if (was == 0) {
                    added.add(partition);
                }
                if (now == 0) {
                    removed.add(partition);
                }
            }
            return new Incremental(from.snapshotId(), to.snapshotId(), added, changed, removed);
        }

        /** 两个快照的分区差异：分区 → (to - from) 文件数变化，只保留变化分区。 */
        public Map<String, Integer> partitionDiff(long fromId, long toId) {
            Snapshot from = snapshot(fromId).orElseThrow(
                    () -> new IllegalStateException("未知快照 id：" + fromId));
            Snapshot to = snapshot(toId).orElseThrow(
                    () -> new IllegalStateException("未知快照 id：" + toId));
            Map<String, Integer> diff = new TreeMap<>();
            Set<String> all = new TreeSet<>(from.filesByPartition().keySet());
            all.addAll(to.filesByPartition().keySet());
            for (String partition : all) {
                int delta = to.filesByPartition().getOrDefault(partition, 0)
                        - from.filesByPartition().getOrDefault(partition, 0);
                if (delta != 0) {
                    diff.put(partition, delta);
                }
            }
            return diff;
        }

        /** 按快照差异得到「需要重算的受影响分区」，按分区升序确定。 */
        public List<String> affectedPartitions(long fromId, long toId) {
            return new ArrayList<>(partitionDiff(fromId, toId).keySet());
        }

        public String chainText() {
            StringBuilder sb = new StringBuilder();
            for (Snapshot snapshot : committed) {
                if (sb.length() > 0) {
                    sb.append(" → ");
                }
                sb.append(snapshot.snapshotId());
                if (snapshot.parentId() != -1L) {
                    sb.append("(parent=").append(snapshot.parentId()).append(")");
                }
            }
            return sb.toString();
        }
    }

    /** 快照：不可变。filesByPartition 是本次提交的清单（分区 → 文件数）。 */
    public record Snapshot(long snapshotId, long parentId, long tsMillis, String operation,
                           Map<String, Integer> filesByPartition) {

        public Snapshot {
            filesByPartition = Collections.unmodifiableMap(new LinkedHashMap<>(filesByPartition));
        }

        public int fileCount() {
            return filesByPartition.values().stream().mapToInt(Integer::intValue).sum();
        }
    }

    /**
     * 一个写者的 CAS 提交结果：它读到的 base、它自己新提交的快照、以及它是不是
     * 「拿下同一个 base」的那个赢家。每个写者恰好汇报一条，因此可以直接断言唯一赢家。
     */
    public record CommitAttempt(String writer, long commitId, long baseId, boolean wonFromBase) {

        public boolean committed() {
            return commitId > 0L;
        }
    }

    /** 增量读结果：自 fromId 到 toId 的分区变化。 */
    public record Incremental(long fromId, long toId, Set<String> addedPartitions,
                              Set<String> changedPartitions, Set<String> removedPartitions) {

        public Incremental {
            addedPartitions = Collections.unmodifiableSet(new LinkedHashSet<>(addedPartitions));
            changedPartitions = Collections.unmodifiableSet(new LinkedHashSet<>(changedPartitions));
            removedPartitions = Collections.unmodifiableSet(new LinkedHashSet<>(removedPartitions));
        }

        public boolean isEmpty() {
            return changedPartitions.isEmpty();
        }

        @Override
        public String toString() {
            return "since " + fromId + " → " + toId + " changed=" + changedPartitions
                    + " added=" + addedPartitions + " removed=" + removedPartitions;
        }
    }

    private static void check(boolean ok, String label) {
        total++;
        if (ok) {
            passed++;
        }
        System.out.println((ok ? "PASS " : "FAIL ") + label);
    }
}
