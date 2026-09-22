// languages/java/ph23-lakehouse-orchestration/examples/ex02-table-snapshots/TableSnapshotsDemo.java —— 快照链主入口：原子提交 + 时间旅行 + 增量读 + schema fail-fast
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex02 *.java && java -cp /tmp/ph23-ex02 TableSnapshotsDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：8/8 PASS）
//
// 场景：两天各追加一批文件，再做一次 compaction 合并；随后 4 个线程并发提交 20 次，用 CAS 证明
// 「没有丢失提交、没有两份当前快照」。断言覆盖 3.2：父链连续、时间旅行、增量读只含变化分区、
// 加列放行、删列/改类型被拒、快照 id 单调。
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Collectors;

public final class TableSnapshotsDemo {

    private static final int TOTAL = 8;

    /** 示例约定：1 个数据文件按 1000 行换算，用来把「文件数」打印成「行数」。 */
    private static final long ROWS_PER_FILE = 1_000L;

    public static void main(String[] args) throws Exception {
        TableFormat table = new TableFormat();

        // 三次顺序提交（时间戳固定，不读系统时钟，保证可复现）
        Snapshot s1 = table.commit("APPEND",
                Map.of("2024-06-01", 2, "2024-06-02", 1), 1_000L);
        Snapshot s2 = table.commit("APPEND",
                Map.of("2024-06-01", 2, "2024-06-02", 3, "2024-06-03", 1), 2_000L);
        Snapshot s3 = table.commit("COMPACT",
                Map.of("2024-06-01", 2, "2024-06-02", 1, "2024-06-03", 1), 3_000L);

        AtomicInteger pass = new AtomicInteger();

        // 1) 父链连续：每个快照的 parentId == 上一个快照的 snapshotId，起点 parentId = -1
        List<Snapshot> chain = table.chain();
        boolean chained = chain.size() == 4;
        for (int i = 1; i < chain.size(); i++) {
            if (chain.get(i - 1).parentId() != chain.get(i).snapshotId()) {
                chained = false;
            }
        }
        chained = chained
                && chain.get(0).equals(s3)
                && s2.parentId() == s1.snapshotId()
                && s3.parentId() == s2.snapshotId()
                && chain.get(chain.size() - 1).parentId() == Snapshot.NO_PARENT;
        check(pass, chained,
                "父链连续：genesis(0) <- s1(1) <- s2(2) <- s3(3)，每段 parentId 都指向上一个快照号");

        // 2) 时间旅行回到历史行数/文件数：2500ms 时应看到 s2（6 个文件 = 6000 行）
        Snapshot at2500 = table.timeTravel(2_500L).orElseThrow();
        Snapshot at1500 = table.timeTravel(1_500L).orElseThrow();
        boolean travelOk = at2500.snapshotId() == s2.snapshotId()
                && at2500.totalFiles() == 6
                && at2500.totalFiles() * ROWS_PER_FILE == 6_000L
                && at1500.snapshotId() == s1.snapshotId()
                && at1500.totalFiles() == 3;
        check(pass, travelOk,
                "时间旅行回到历史行数/文件数：t=2500ms 读到 s2（6 文件 / 6000 行），t=1500ms 读到 s1（3 文件 / 3000 行）");

        // 3) 增量读只含变化分区：从 s1 看变化是 06-03（新增），从 s2 看变化是 06-02（3 -> 1 被合并）
        Map<String, Integer> fromS1 = table.incremental(s1.snapshotId());
        Map<String, Integer> fromS2 = table.incremental(s2.snapshotId());
        check(pass, fromS1.keySet().equals(Set.of("2024-06-03"))
                        && fromS2.keySet().equals(Set.of("2024-06-02")),
                "增量读只含变化分区：自 s1 起 = {2024-06-03}，自 s2 起 = {2024-06-02}（未变分区不返回）");

        // 4) 加列通过：ADD COLUMN 对旧数据是安全的（历史文件该列读作 null）
        table.evolveSchema("ADD COLUMN latency_p99_ms BIGINT");
        check(pass, table.schema().contains("latency_p99_ms") && table.schema().size() == 3,
                "加列通过：ADD COLUMN latency_p99_ms 生效，schema = " + table.schema());

        // 5) 删列被拒：历史文件读不出来，必须在提交阶段拦下
        String dropMessage = "";
        boolean dropRejected = false;
        try {
            table.evolveSchema("DROP COLUMN event_ts");
        } catch (IllegalStateException e) {
            dropRejected = true;
            dropMessage = e.getMessage();
        }
        check(pass, dropRejected && dropMessage.contains("DROP COLUMN event_ts")
                        && dropMessage.contains("历史快照") && table.schema().contains("event_ts"),
                "删列被拒：DROP COLUMN 抛 IllegalStateException 并给出原因，列仍保留");

        // 6) 改类型被拒：下游类型断言会全崩
        String changeMessage = "";
        boolean changeRejected = false;
        try {
            table.evolveSchema("CHANGE TYPE event_ts STRING");
        } catch (IllegalStateException e) {
            changeRejected = true;
            changeMessage = e.getMessage();
        }
        check(pass, changeRejected && changeMessage.contains("CHANGE TYPE")
                        && changeMessage.contains("类型"),
                "改类型被拒：CHANGE TYPE 抛 IllegalStateException 并给出原因");

        // 7) CAS 提交后 current 是新快照：4 线程 × 5 次并发提交，一次都不能丢
        List<Long> committedIds = Collections.synchronizedList(new ArrayList<>());
        int threads = 4;
        int perThread = 5;
        Thread[] workers = new Thread[threads];
        for (int i = 0; i < threads; i++) {
            final int ti = i;
            workers[i] = new Thread(() -> {
                for (int j = 0; j < perThread; j++) {
                    // 固定时间戳：并发提交也不读系统时钟
                    long ts = 4_000L + ti * 100L + j;
                    Map<String, Integer> files = new TreeMap<>();
                    files.put(String.format("2024-06-0%d", (ti % 3) + 1), j + 1);
                    Snapshot s = table.commit("CONCURRENT_APPEND", files, ts);
                    committedIds.add(s.snapshotId());
                }
            }, "committer-" + i);
            workers[i].start();
        }
        for (Thread w : workers) {
            w.join();   // 等全部提交结束再读，避免读到「CAS 成功但还没登记 history」的中间态
        }

        List<Snapshot> finalChain = table.chain();
        Set<Long> chainIds = finalChain.stream().map(Snapshot::snapshotId).collect(Collectors.toSet());
        boolean allLanded = committedIds.stream().allMatch(chainIds::contains);
        check(pass, table.commitCount() == 3 + threads * perThread
                        && finalChain.size() == 24
                        && finalChain.get(0).snapshotId() == 23
                        && allLanded,
                "CAS 提交后 current 是新快照：23 次提交全部落链（链长 24），并发冲突重试 "
                        + table.casRetries() + " 次，无丢失提交");

        // 8) 快照 id 单调：沿链严格递减且首尾相邻（id = parentId + 1，无空洞）
        boolean strictlyDescending = true;
        boolean contiguous = true;
        for (int i = 1; i < finalChain.size(); i++) {
            if (finalChain.get(i - 1).snapshotId() <= finalChain.get(i).snapshotId()) {
                strictlyDescending = false;
            }
            if (finalChain.get(i - 1).snapshotId() - 1 != finalChain.get(i).snapshotId()) {
                contiguous = false;
            }
        }
        check(pass, strictlyDescending && contiguous,
                "快照 id 单调：链上 23 -> 0 严格递减且相邻（id = parentId + 1，不依赖时间戳）");

        System.out.println("== 快照链（最新在前） ==");
        for (Snapshot s : finalChain) {
            if (s.snapshotId() >= 20 || s.snapshotId() <= 3) {
                System.out.printf("  #%-2d parent=%-2d ts=%-5d op=%-18s files=%s%n",
                        s.snapshotId(), s.parentId(), s.tsMillis(), s.operation(), s.filesByPartition());
            }
        }

        if (pass.get() == TOTAL) {
            System.out.printf("ALL PASS: %d/%d%n", pass.get(), TOTAL);
        } else {
            System.out.printf("FAILED: %d/%d（详见上面的 FAIL 行）%n", pass.get(), TOTAL);
            System.exit(1);
        }
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
