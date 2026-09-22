// exercises/sol-04-batch-write-optimization.java —— 练习 4 参考实现：批量写入优化（roadmap ph18 练习：批量写入优化）
// 目标还原（见 exercises/README.md）：同一批写操作，比较「逐条写 / 攒批写 / 管道写」三种方式的
//   网络往返次数，并验证最终落库状态一致 —— 优化的是「往返」，不是「语义」。
//   生产对应（主文档 3.9 异步化与批处理）：
//     - 逐条写：每条 INSERT/SET 等一次响应 → 网络往返 = 条数
//     - 攒批写：内存 buffer 攒满/到点再落库（JDBC addBatch、MySQL 批量 INSERT、MQ 批量投递）
//     - 管道写：Redis Pipeline —— 命令一条不省，但一趟 RTT 送达一批，服务端按序执行（MGET/MSET 同理）
//   计量模型（与真实网络一一对应）：
//     executedOps = 服务端实际执行的命令条数（三路都必须是 500，优化不该少干活）；
//     roundTrips  = 客户端等服务器响应的次数（逐条 500 → 攒批 5 → 管道 1，这才是优化点）。
//   服务端执行顺序由「收到的顺序」决定；重复 key 后写覆盖先写 —— 三路最终状态必须一致。
// 教学性覆盖：真实批量还有失败重试、单批大小上限、批量窗口延迟等工程细节（ph17 已涉及其一部分），
//             本练习聚焦「一条命令=一次往返 vs 一批命令=一次往返」这个吞吐差异的根源。
// 验证环境：OpenJDK 17（javac -version -> 17.x）；无第三方依赖
// 验证命令：
//   # 1. 编译（在 exercises/ 目录下执行）
//   javac sol-04-batch-write-optimization.java
//   # 2. 运行
//   java BatchWriteOptimizationDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：javac 编译通过、运行全部 PASS）

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 批量写入优化练习参考实现：逐条 / 攒批 / 管道 三种写路径的往返次数对比 */
final class BatchWriteOptimizationDemo {

    /** 写操作：key-value（同 key 可重复写 = 覆盖） */
    record WriteOp(String key, String value) {
    }

    /**
     * 远端存储（模拟数据库/Redis）：
     *   executedOps —— 服务端执行条数；roundTrips —— 客户端等待响应的次数。
     *   服务端按收到顺序执行（LinkedHashMap 记录落库顺序）。
     */
    static final class RemoteStore {
        private final Map<String, String> data = new LinkedHashMap<>();
        private int executedOps;
        private int roundTrips;

        /** 逐条送达：执行 1 条 + 等 1 次响应 */
        void execSingle(WriteOp op) {
            applyOne(op);
            roundTrips++;
        }

        /** 批量送达：一批命令装进一次请求，服务端顺序执行；只等 1 次响应 */
        void execBatch(List<WriteOp> ops) {
            for (WriteOp op : ops) {
                applyOne(op);
            }
            roundTrips++;
        }

        private void applyOne(WriteOp op) {
            data.put(op.key(), op.value());
            executedOps++;
        }

        int executedOps() {
            return executedOps;
        }

        int roundTrips() {
            return roundTrips;
        }

        Map<String, String> snapshot() {
            return Map.copyOf(data);
        }
    }

    /** 攒批写入器：buffer 攒满 batchSize 才发一批（JDBC addBatch / 批量 INSERT 的同一思想） */
    static final class BufferedWriter {
        private final RemoteStore store;
        private final int batchSize;
        private final List<WriteOp> buffer = new ArrayList<>();
        private int batches;

        BufferedWriter(RemoteStore store, int batchSize) {
            this.store = store;
            this.batchSize = batchSize;
        }

        void write(WriteOp op) {
            buffer.add(op);
            if (buffer.size() >= batchSize) {
                flush();
            }
        }

        /** 收尾：把不足一批的剩余也发掉 */
        void flush() {
            if (buffer.isEmpty()) {
                return;
            }
            store.execBatch(new ArrayList<>(buffer));
            buffer.clear();
            batches++;
        }

        int batches() {
            return batches;
        }
    }

    /** 造一批写操作：500 条；每两个 key 一组（重复写两次 = 最后一次覆盖），共 250 个 key */
    static List<WriteOp> workload(int n) {
        List<WriteOp> ops = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            ops.add(new WriteOp("k" + (i / 2), "v" + i));
        }
        return ops;
    }

    static void check(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError("自检失败: " + label);
        }
        System.out.println("PASS  " + label);
    }

    public static void main(String[] args) {
        List<WriteOp> ops = workload(500);
        check(ops.size() == 500, "工作负载：500 条写（250 个 key 各写两次，最后一次覆盖前一次）");

        System.out.println("路径 A：逐条写 —— 每条命令都等一次服务器响应");
        RemoteStore a = new RemoteStore();
        for (WriteOp op : ops) {
            a.execSingle(op);
        }
        check(a.roundTrips() == 500, "逐条写 roundTrips = " + a.roundTrips() + "（= 命令条数，RTT 全花在等待上）");
        check(a.executedOps() == 500, "服务端确实执行了 500 条（没有偷工减料）");

        System.out.println("路径 B：攒批写 —— buffer 攒满 100 条才发一批");
        RemoteStore b = new RemoteStore();
        BufferedWriter buffered = new BufferedWriter(b, 100);
        for (WriteOp op : ops) {
            buffered.write(op);
        }
        buffered.flush();
        check(buffered.batches() == 5, "500 条被分成 5 批（每批 100）");
        check(b.roundTrips() == 5, "攒批写 roundTrips = " + b.roundTrips() + "（5 批 × 每批 1 次往返，等待从 500 降到 5）");
        check(b.executedOps() == 500, "服务端执行的仍是 500 条 —— 攒批省的是往返，不省执行");

        System.out.println("路径 C：管道写 —— 500 条命令装进 1 趟往返送达（Redis Pipeline 语义）");
        RemoteStore c = new RemoteStore();
        c.execBatch(ops);
        check(c.roundTrips() == 1, "管道写 roundTrips = " + c.roundTrips() + "（一趟 RTT 送达全部命令，服务端按序执行）");
        check(c.executedOps() == 500, "服务端逐条执行了 500 条（Redis 单线程保证顺序，见主文档 4.1）");

        System.out.println("最终一致性 —— 三种路径落库结果必须完全相同（这是优化的前提）：");
        check(a.snapshot().equals(b.snapshot()) && a.snapshot().equals(c.snapshot()),
                "逐条/攒批/管道最终存储完全一致（重复 key 覆盖语义保持，无乱序）");
        check(a.snapshot().size() == 250, "250 个 key 每个只留最后一次写入的值");
        check(a.snapshot().get("k0").equals("v1") && a.snapshot().get("k249").equals("v499"),
                "k0 的最后一次写是 v1、k249 的最后一次写是 v499 —— 覆盖顺序按原始序列，三种路径一致");
        System.out.println();
        System.out.println("对照汇总：");
        System.out.println("  | 路径   | roundTrips | executedOps |");
        System.out.println("  | 逐条写 | " + a.roundTrips() + " | " + a.executedOps() + " |");
        System.out.println("  | 攒批写 | " + b.roundTrips() + " | " + b.executedOps() + " |");
        System.out.println("  | 管道写 | " + c.roundTrips() + " | " + c.executedOps() + " |");
        System.out.println("结论：吞吐瓶颈常在「往返等待」；攒批/管道把等待从 O(条数) 降到 O(批数/1)。");
        System.out.println("对照主文档 3.9：批量优化的代价是失败重放整批、延迟可见窗口、内存积压 —— 取舍着用。");
    }
}
