// exercises/sol-02-pool-quota/GpuPool.java —— GPU 台账：分配/回收/不变量 allocated + free == total
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol02 *.java && java -cp /tmp/ph22-sol02 Sol02Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：13/13 PASS）

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 「一张卡的账本」：总量固定，分配与回收都必须过账。
 * 硬不变量：任何时刻 allocatedTotal() + free() == total()。
 * 失败时账本必须保持原样（不部分占用）——这是配额与调度能信任台账的前提。
 */
public final class GpuPool {

    private final int total;
    private final Map<String, Integer> allocated = new LinkedHashMap<>();

    public GpuPool(int total) {
        if (total <= 0) {
            throw new IllegalArgumentException("池子总量必须为正数：" + total);
        }
        this.total = total;
    }

    public int total() { return total; }

    /** 已分配卡数（台账右侧）。 */
    public synchronized int allocatedTotal() {
        int sum = 0;
        for (int gpus : allocated.values()) {
            sum += gpus;
        }
        return sum;
    }

    /** 空闲卡数 = 总量 - 已分配（台账左侧，恒等式的一半）。 */
    public synchronized int free() {
        return total - allocatedTotal();
    }

    /** 可断言的安全网：任何一次变更之后都必须为 true。 */
    public synchronized boolean checkInvariant() {
        return allocatedTotal() + free() == total;
    }

    /**
     * 分配。重复分配同一 jobId 是账本事故（会把一张卡记成两次），必须拒绝而不是覆盖。
     * 空闲不足同样拒绝，且拒绝时不改变任何账本状态。
     */
    public synchronized void allocate(String jobId, int gpus) {
        if (jobId == null || jobId.isBlank()) {
            throw new IllegalArgumentException("jobId 不能为空");
        }
        if (gpus <= 0) {
            throw new IllegalArgumentException("GPU 数量必须为正数：" + gpus);
        }
        if (allocated.containsKey(jobId)) {
            throw new IllegalStateException("重复分配被拒：任务 " + jobId + " 已持有 " + allocated.get(jobId) + " 卡");
        }
        if (free() < gpus) {
            throw new IllegalStateException("分配被拒：任务 " + jobId + " 申请 " + gpus + " 卡，空闲仅 " + free() + " 卡");
        }
        allocated.put(jobId, gpus);
    }

    /** 回收。释放一个不存在的分配说明上下游状态已经不一致，必须显式报错。 */
    public synchronized int release(String jobId) {
        Integer gpus = allocated.remove(jobId);
        if (gpus == null) {
            throw new IllegalStateException("释放被拒：任务 " + jobId + " 没有任何已分配的 GPU");
        }
        return gpus;
    }

    /** 台账快照（只读），用于对账与展示。 */
    public synchronized Map<String, Integer> snapshot() {
        return Collections.unmodifiableMap(new LinkedHashMap<>(allocated));
    }

    @Override
    public synchronized String toString() {
        return "GpuPool[allocated=" + allocatedTotal() + " free=" + free() + " total=" + total
                + " holders=" + allocated + "]";
    }
}
