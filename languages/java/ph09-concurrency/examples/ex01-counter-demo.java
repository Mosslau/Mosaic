// examples/ex01-counter-demo.java —— 多线程计数器：普通变量 vs synchronized vs AtomicInteger
// 对应主文档 6. 示例 1：10 线程各加 1 万次，对比三种写法的正确性
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex01-counter-demo.java
// 运行：java CounterDemo（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
// 运行前提：plain 计数故意不加锁（竞态演示），其结果通常小于期望值——这是预期的演示效果，不是 bug
import java.util.concurrent.atomic.AtomicInteger;

class CounterDemo {
    static int plain = 0;                              // 非原子：读-改-写三步被线程交错，丢更新
    static int sync = 0;
    static final AtomicInteger atomic = new AtomicInteger();

    public static void main(String[] args) throws InterruptedException {
        final int N = 10_000;                          // 每线程加 N 次
        final int THREADS = 10;
        Thread[] threads = new Thread[THREADS];
        for (int i = 0; i < THREADS; i++) {
            threads[i] = new Thread(() -> {
                for (int j = 0; j < N; j++) {
                    plain++;                           // 竞态：非原子，结果不确定
                    synchronized (CounterDemo.class) { // 加锁：原子且可见
                        sync++;
                    }
                    atomic.incrementAndGet();          // CAS：无锁且原子
                }
            });
        }
        for (Thread t : threads) t.start();
        for (Thread t : threads) t.join();             // 主线程等全部线程结束再读结果

        int expect = N * THREADS;
        System.out.println("期望值    = " + expect);
        System.out.println("plain     = " + plain + "  (通常小于期望值: " + (plain < expect) + ")");
        System.out.println("sync      = " + sync + "  (正确: " + (sync == expect) + ")");
        System.out.println("atomic    = " + atomic.get() + "  (正确: " + (atomic.get() == expect) + ")");
        if (sync != expect || atomic.get() != expect) {
            throw new AssertionError("sync/atomic 计数不一致——同步原语失效");
        }
        System.out.println("自检通过：synchronized 与 AtomicInteger 计数均为 " + expect);
    }
}
