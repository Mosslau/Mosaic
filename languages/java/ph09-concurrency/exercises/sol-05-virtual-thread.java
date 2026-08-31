// exercises/sol-05-virtual-thread.java —— 练习 5 参考实现：用虚拟线程实现高并发任务处理（对比平台线程池）
// 验证环境：需 JDK 21+（虚拟线程 API 自 Java 21 正式化）
// 编译：javac sol-05-virtual-thread.java
// 运行：java VirtualThreadSol（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 25.0.2（Homebrew openjdk@25；OpenJDK 17 无法编译本文件）
import java.time.Duration;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

class VirtualThreadSol {
    static final int TASKS = 10_000;

    public static void main(String[] args) throws Exception {
        long platform = run(Executors.newFixedThreadPool(200));
        long virtual = run(Executors.newVirtualThreadPerTaskExecutor());
        System.out.printf("平台线程池(200 线程): %d ms%n", platform);
        System.out.printf("虚拟线程(每任务一线程): %d ms%n", virtual);
        System.out.println("结论：阻塞 IO 场景虚拟线程远快于固定线程池（阻塞时自动让出载体线程）；"
                + "换成纯 CPU 计算则无此优势——计算密集任务不要用虚拟线程");
    }

    /** 提交 TASKS 个各阻塞 10ms 的任务，等待全部完成，返回耗时 ms；断言一个不落 */
    static long run(ExecutorService pool) throws InterruptedException {
        long start = System.nanoTime();
        AtomicInteger done = new AtomicInteger();
        try (pool) {                               // JDK 21+：ExecutorService 实现 AutoCloseable，关闭即等待收尾
            for (int i = 0; i < TASKS; i++) {
                pool.submit(() -> {
                    try {
                        Thread.sleep(Duration.ofMillis(10));   // 模拟阻塞 IO
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    } finally {
                        done.incrementAndGet();
                    }
                });
            }
        }
        if (done.get() != TASKS) throw new AssertionError("有任务未完成: " + done.get());
        return TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - start);
    }
}
