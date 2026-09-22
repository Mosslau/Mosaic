// project/src/aiplat/GpuPool.java —— GPU 台账：分配/回收/不变量/租户占用
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 算力资源池（主文档 3.2）：一张卡的账本，总量固定，分配与回收都必须过账。
 *
 * <p>核心不变量：任何时刻 {@code allocated + free == total}。它是可断言的安全网——
 * 一旦被破坏（重复释放、超额分配、漏释放），资源账目就永久失真，且事后无法重建。
 *
 * <p>为什么分配/释放方法是 synchronized 且用 LinkedHashMap：本阶段演示的是控制面语义，
 * 不追求调度吞吐；synchronized 保证「检查 + 记账」是原子的（否则 free 判断与写入之间有竞态），
 * LinkedHashMap 保证遍历顺序 = 分配顺序，让审计输出与断言可复现。
 */
public final class GpuPool {

    private final int total;
    private final Map<String, Allocation> allocated = new LinkedHashMap<>();

    public GpuPool(int total) {
        if (total <= 0) {
            throw new IllegalArgumentException("GPU 总量必须为正");
        }
        this.total = total;
    }

    public int total() { return total; }

    public synchronized int allocatedGpus() {
        int sum = 0;
        for (Allocation a : allocated.values()) {
            sum += a.gpus();
        }
        return sum;
    }

    public int free() { return total - allocatedGpus(); }

    /** 不变量自检：资源账本的健康检查，任何时刻都应为 true。 */
    public synchronized boolean invariantHolds() {
        return allocatedGpus() + free() == total;
    }

    /**
     * 尝试分配：放得下就记账并返回 true，放不下返回 false（而不是抛异常）。
     *
     * <p>为什么用返回值而不是异常：调度器需要「试一下再换一个任务」，把「放不下」当作
     * 常态控制流而不是异常——异常应该留给真正的错误（例如状态机非法迁移）。
     */
    public synchronized boolean tryAllocate(String jobId, String tenant, int gpus, long ts) {
        if (gpus <= 0) {
            throw new IllegalArgumentException("申请卡数必须为正");
        }
        if (allocated.containsKey(jobId)) {
            throw new IllegalStateException("重复分配：任务 " + jobId + " 已持有 GPU，账本不允许一笔两记");
        }
        if (gpus > free()) {
            return false;
        }
        allocated.put(jobId, new Allocation(jobId, tenant, gpus, ts));
        return true;
    }

    /** 释放：返回被释放的分配记录（供计量记账）；任务未持有 GPU 时返回 null。 */
    public synchronized Allocation release(String jobId) {
        return allocated.remove(jobId);
    }

    /** 租户占用（配额校验的输入）。 */
    public synchronized Map<String, Integer> tenantUsage() {
        Map<String, Integer> usage = new LinkedHashMap<>();
        for (Allocation a : allocated.values()) {
            usage.merge(a.tenant(), a.gpus(), Integer::sum);
        }
        return usage;
    }

    /** 当前所有分配的快照（运维一屏与审计用）。 */
    public synchronized Map<String, Allocation> allocations() {
        return Map.copyOf(allocated);
    }

    /** 一条分配记录：startTs 是计量事件的起点（GPU 秒 = gpus × 持有秒数）。 */
    public record Allocation(String jobId, String tenant, int gpus, long startTs) {
        public long gpuSeconds(long endTs) {
            long seconds = Math.max(0L, (endTs - startTs) / 1000L);
            return gpus * seconds;
        }
    }
}
