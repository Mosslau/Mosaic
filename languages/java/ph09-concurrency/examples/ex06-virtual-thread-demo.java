// examples/ex06-virtual-thread-demo.java —— 虚拟线程 vs 平台线程：阻塞 IO 场景的并发能力对比
// 对应主文档 6. 示例 6：1 万个各阻塞 10ms 的任务，固定 200 线程的平台池 vs 每任务一线程的虚拟线程
// 验证环境：需 JDK 21+（newVirtualThreadPerTaskExecutor / Thread.sleep(Duration) /
//           ExecutorService 实现 AutoCloseable 均为 Java 21 特性）
// 编译：javac ex06-virtual-thread-demo.java
// 运行：java VirtualThreadDemo（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 25.0.2（Homebrew openjdk@25；虚拟线程 API 自 Java 21 正式化，
//           OpenJDK 17 无法编译本文件）
import java.time.Duration;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

class VirtualThreadDemo {
    static final int TASKS = 10_000;

    public static void main(String[] args) throws Exception {
        long platform = run(Executors.newFixedThreadPool(200), "平台线程池(200 线程)");
        long virtual = run(Executors.newVirtualThreadPerTaskExecutor(), "虚拟线程(每任务一线程)");
        System.out.printf("平台线程池(200 线程): %d ms%n", platform);
        System.out.printf("虚拟线程: %d ms%n", virtual);
        System.out.println("说明：阻塞 IO 场景虚拟线程自动让出载体线程，1 万个阻塞任务近乎瞬时完成；"
                + "结论可复现，具体毫秒数随机器而异");
    }

    /** 提交 TASKS 个各阻塞 10ms 的任务，等待全部完成，返回总耗时（ms）；断言一个不落 */
    static long run(ExecutorService pool, String tag) throws InterruptedException {
        long start = System.nanoTime();
        AtomicInteger done = new AtomicInteger();
        try (pool) {                              // JDK 21+：ExecutorService 是 AutoCloseable，关闭即等待收尾
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
        long ms = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - start);
        if (done.get() != TASKS) throw new AssertionError(tag + " 有任务未完成: " + done.get());
        System.out.println(tag + " 完成数 = " + done.get() + " / " + TASKS);
        return ms;
    }
}
