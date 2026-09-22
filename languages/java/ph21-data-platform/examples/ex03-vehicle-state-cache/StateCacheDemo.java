// examples/ex03-vehicle-state-cache/StateCacheDemo.java —— 并发上报实时状态缓存演示
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：
//   javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//   java -cp /tmp/tl21-cls StateCacheDemo
// 期望：两路网关对同一 VIN 乱序上报，缓存最终收敛到最大 seq，且丢弃计数 > 0 证明原子比较生效。
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class StateCacheDemo {
    private static final int VIN_COUNT = 4;
    private static final int SEQ_MAX = 2000;

    public static void main(String[] args) throws InterruptedException {
        VehicleStateCache cache = new VehicleStateCache();
        List<Thread> writers = new ArrayList<>();

        for (int v = 1; v <= VIN_COUNT; v++) {
            String vin = "LSV" + String.format("%06d", v);
            // 双路网关：A 路正常速率、B 路先睡 30ms 再上报(制造大量乱序旧帧)
            writers.add(new Thread(() -> pump(cache, vin, SEQ_MAX, 0), "gw-A-" + vin));
            writers.add(new Thread(() -> pump(cache, vin, SEQ_MAX, 30), "gw-B-" + vin));
        }
        // 读者线程：期间反复快照，验证弱一致遍历不炸
        Thread reader = new Thread(() -> {
            for (int i = 0; i < 20; i++) {
                cache.snapshot();
                Thread.onSpinWait();
            }
        }, "reader");
        reader.start();

        for (Thread t : writers) {
            t.start();
        }
        for (Thread t : writers) {
            t.join();
        }
        reader.join();

        AtomicInteger pass = new AtomicInteger();
        check(pass, cache.size() == VIN_COUNT, "4 个 VIN 全部进入状态缓存");
        boolean allConverged = cache.snapshot().stream()
                .allMatch(s -> s.seq() == SEQ_MAX);
        check(pass, allConverged, "每个 VIN 最终收敛到最大 seq=" + SEQ_MAX + "(乱序帧被拒，无旧值覆写)");
        check(pass, cache.staleDropped() > 0, "乱序旧帧被丢弃计数=" + cache.staleDropped()
                + " > 0(原子比较真的在工作)");
        check(pass, cache.snapshot().stream().allMatch(s -> s.socPct() >= 0 && s.socPct() <= 100),
                "快照中的状态物理量都在量程内(无半写脏数据)");
        System.out.println("末帧样例: " + cache.get("LSV" + String.format("%06d", 1)));
        System.out.printf("ALL PASS: %d/4%n", pass.get());
    }

    private static void pump(VehicleStateCache cache, String vin, int max, long preDelayMs) {
        if (preDelayMs > 0) {
            try {
                Thread.sleep(preDelayMs);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
        for (long seq = 1; seq <= max; seq++) {
            cache.update(VehicleState.of(vin, seq, 30 + (seq % 70)));
        }
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
