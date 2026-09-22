// languages/java/ph22-ai-platform/examples/ex02-gpu-pool/GpuPoolDemo.java —— GPU 池主入口：分配/回收/不变量/租户占用
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex02 *.java && java -cp /tmp/ph22-ex02 GpuPoolDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：10/10 PASS）
//
// 场景：16 卡的池子，两个租户提交三个任务；一次超量申请被拒，一次重复分配被拒，
// 一次释放不存在的 jobId 被拒；任务结束后回收的卡立刻能被新任务复用。
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

public final class GpuPoolDemo {
    /** 断言总数：用于末尾 ALL PASS: N/N 与失败退出码，避免手工维护分母时数错。 */
    private static final int TOTAL_CHECKS = 10;

    public static void main(String[] args) {
        GpuPool pool = new GpuPool(16);
        Map<String, String> jobTenant = new HashMap<>();   // jobId → tenant（真实平台在任务台账里）

        AtomicInteger pass = new AtomicInteger();

        // 1) 分配后不变量成立：8 + 4 张卡出手，剩 4 张，allocated + free == total
        check(pass, pool.tryAllocate("job-001", 8), "job-001 申请 8 卡成功");
        jobTenant.put("job-001", "acme");
        check(pass, pool.tryAllocate("job-002", 4), "job-002 申请 4 卡成功");
        jobTenant.put("job-002", "beta");
        check(pass, pool.free() == 4 && pool.allocatedTotal() == 12
                        && pool.allocatedTotal() + pool.free() == pool.total(),
                "分配后不变量成立：allocated(12) + free(4) == total(16)");

        // 2) 超量申请返回 false 且状态不变（容量不足是正常输入，不是异常）
        int freeBefore = pool.free();
        int countBefore = pool.allocationCount();
        boolean tooBig = pool.tryAllocate("job-003", 8);
        check(pass, !tooBig && pool.free() == freeBefore && pool.allocationCount() == countBefore,
                "超量申请 8 卡 > free 4 卡：返回 false 且池状态完全不变");

        // 3) 重复分配同一 jobId 被拒：同一任务不能占两份卡
        boolean duplicateRejected = false;
        try {
            pool.tryAllocate("job-001", 2);
        } catch (IllegalStateException e) {
            duplicateRejected = true;
        }
        check(pass, duplicateRejected, "重复分配同一 jobId 抛 IllegalStateException");

        // 4) 释放不存在的 jobId 被拒：静默容忍会把调用方状态错误埋到线上
        boolean missingReleaseRejected = false;
        try {
            pool.release("job-999");
        } catch (IllegalStateException e) {
            missingReleaseRejected = true;
        }
        check(pass, missingReleaseRejected, "释放不存在的 jobId 抛 IllegalStateException");

        // 5) 释放后可复用：job-002 归还 4 卡，beta 用同样 4 卡让 job-003 进场
        pool.release("job-002");
        boolean reused = pool.tryAllocate("job-003", 4);
        jobTenant.put("job-003", "beta");
        check(pass, reused && pool.free() == 4, "释放 4 卡后 job-003 复用成功，free 回到 4");

        // 6) 池被占满后新申请被拒；租户占用统计精确（逐租户之和 == allocated 总量）
        check(pass, pool.tryAllocate("job-004", 4), "job-004 吃掉最后 4 卡，池占满");
        jobTenant.put("job-004", "beta");
        check(pass, pool.free() == 0 && !pool.tryAllocate("job-005", 1),
                "池满时 job-005 申请 1 卡被拒（返回 false）");
        check(pass, pool.allocatedOf("acme", jobTenant) == 8
                        && pool.allocatedOf("beta", jobTenant) == 8
                        && pool.allocatedOf("gamma", jobTenant) == 0
                        && pool.allocatedOf("acme", jobTenant) + pool.allocatedOf("beta", jobTenant)
                            == pool.allocatedTotal(),
                "租户占用统计：acme=8 beta=8 gamma=0，逐租户之和 == allocated 总量");

        System.out.println("== 资金账本快照（jobId → 卡数） ==");
        pool.snapshot().forEach((jobId, gpus) ->
                System.out.printf("  %-8s %d 卡  tenant=%s%n", jobId, gpus, jobTenant.get(jobId)));
        System.out.printf("  total=%d allocated=%d free=%d%n",
                pool.total(), pool.allocatedTotal(), pool.free());
        System.out.printf("ALL PASS: %d/%d%n", pass.get(), TOTAL_CHECKS);
        if (pass.get() != TOTAL_CHECKS) {
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
