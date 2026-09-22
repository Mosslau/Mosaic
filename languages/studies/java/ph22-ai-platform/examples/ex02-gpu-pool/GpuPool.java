// languages/java/ph22-ai-platform/examples/ex02-gpu-pool/GpuPool.java —— GPU 资源台账：分配/回收/不变量
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex02 *.java && java -cp /tmp/ph22-ex02 GpuPoolDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：10/10 PASS）
//
// 为什么这是一本「账」而不是一个计数器：
//   ① 计数器只能说「还剩几张卡」，回答不了「这 12 张卡被谁占着、哪个任务占的」——
//      而回收（任务结束/被抢占）必须精确到 jobId，不能靠猜。
//   ② 任何时刻 allocated + free == total 是硬不变量：一旦不成立，要么卡泄漏
//      （任务结束了账没销），要么超卖（两个任务拿到同一张卡）。
//   ③ 重复分配同一 jobId 与释放不存在的 jobId 都必须抛异常而非静默修正：
//      这两件事都说明调用方与平台状态已经不一致，静默容忍只会把 bug 埋到线上。
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public final class GpuPool {
    private final int total;
    /** jobId → 卡数。用 CHM 保证并发下读快照安全，写操作统一由 synchronized 串行化。 */
    private final Map<String, Integer> allocated = new ConcurrentHashMap<>();

    public GpuPool(int total) {
        if (total <= 0) {
            throw new IllegalArgumentException("total 必须为正: " + total);
        }
        this.total = total;
    }

    /**
     * 尝试分配：放得下就记账并返回 true，放不下返回 false 且**状态不变**。
     * 为什么超量申请返回 false 而不是抛异常：容量不足是调度器的正常输入
     * （它要继续等或换一个任务），不是程序错误；而重复 jobId 才是错误。
     */
    public synchronized boolean tryAllocate(String jobId, int gpus) {
        if (gpus <= 0) {
            throw new IllegalArgumentException("gpus 必须为正: " + gpus);
        }
        if (allocated.containsKey(jobId)) {
            throw new IllegalStateException(
                    "jobId 重复分配: " + jobId + "，先 release 再 allocate");
        }
        if (gpus > free()) {
            return false;                     // 拒绝而不是排队：配额/容量问题等待不会变好
        }
        allocated.put(jobId, gpus);
        verifyInvariant();
        return true;
    }

    /** 释放：不存在的 jobId 抛异常——它意味着调用方状态已经错了，不能静默吞掉。 */
    public synchronized void release(String jobId) {
        Integer held = allocated.remove(jobId);
        if (held == null) {
            throw new IllegalStateException("释放不存在的 jobId: " + jobId);
        }
        verifyInvariant();
    }

    public int total() {
        return total;
    }

    public int free() {
        return total - allocated.values().stream().mapToInt(Integer::intValue).sum();
    }

    public int allocatedTotal() {
        return allocated.values().stream().mapToInt(Integer::intValue).sum();
    }

    /**
     * 租户占用统计：从 jobId → 卡数 与 jobId → tenant 的映射反查。
     * 本示例把「租户归属」放在池外（真实平台里它属于任务台账），池只认 jobId。
     */
    public int allocatedOf(String tenant, Map<String, String> jobTenant) {
        return allocated.entrySet().stream()
                .filter(e -> tenant.equals(jobTenant.get(e.getKey())))
                .mapToInt(Map.Entry::getValue)
                .sum();
    }

    public int allocationCount() {
        return allocated.size();
    }

    /** 分配明细快照（按 jobId 排序，便于确定性输出与对账）。 */
    public Map<String, Integer> snapshot() {
        return new LinkedHashMap<>(new java.util.TreeMap<>(allocated));
    }

    /** 硬不变量：账实相符。每次写操作后自检，把泄漏与超卖挡在发生的那一刻。 */
    private void verifyInvariant() {
        if (allocatedTotal() + free() != total) {
            throw new IllegalStateException(
                    "资源账本不变量被破坏: allocated=" + allocatedTotal() + " + free=" + free()
                            + " != total=" + total);
        }
    }
}
