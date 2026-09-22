// exercises/sol-01-counter.java —— 练习 1 参考实现：多线程计数器（10 线程 × 1 万次）
// 验证环境：OpenJDK 17.0.18
// 编译：javac sol-01-counter.java
// 运行：java CounterSol（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
// 运行前提：plain 计数故意不加锁（演示竞态），其结果通常小于期望值——这是预期的演示效果，不是 bug
import java.util.concurrent.atomic.AtomicInteger;

class CounterSol {
    static int plain;                       // 竞态：结果不确定
    static int sync;
    static final AtomicInteger atomic = new AtomicInteger();

    public static void main(String[] args) throws InterruptedException {
        final int N = 10_000, T = 10;
        Thread[] threads = new Thread[T];
        for (int i = 0; i < T; i++) {
            threads[i] = new Thread(() -> {
                for (int j = 0; j < N; j++) {
                    plain++;
                    synchronized (CounterSol.class) { sync++; }
                    atomic.incrementAndGet();
                }
            });
        }
        for (Thread t : threads) t.start();
        for (Thread t : threads) t.join();  // 必须等全部线程结束再读结果

        int expect = N * T;
        System.out.println("期望值    = " + expect);
        System.out.println("plain     = " + plain + "  (通常 < 期望值)");
        System.out.println("sync      = " + sync + "  (正确: " + (sync == expect) + ")");
        System.out.println("atomic    = " + atomic.get() + "  (正确: " + (atomic.get() == expect) + ")");
        if (sync != expect || atomic.get() != expect) {
            throw new AssertionError("sync/atomic 计数与期望不符");
        }
        System.out.println("自检通过：synchronized 与 AtomicInteger 计数均为 " + expect);
    }
}
