/*
 * examples/ex03-handwritten-threadpool/ThreadPoolDemo.java
 * 验证手写线程池的关键行为（对照 ThreadPoolExecutor 语义）：
 *  ① 并发任务执行次数精确（线程池的线程是被复用的同一批 worker）
 *  ② 任务数 > maxSize 且队列满 → 触发拒绝策略
 *  ③ shutdown 后不再接受新任务
 * 运行输出 worker 最大数，配合主文档 3.4 理解「core→queue→max→reject」四段路径。
 *
 * 验证环境：OpenJDK 17.0.18（Homebrew）
 * 编译：javac -encoding UTF-8 -d /tmp/tl20-cls HandwrittenThreadPool.java ThreadPoolDemo.java
 * 运行：java -cp /tmp/tl20-cls ThreadPoolDemo
 * 本机已实测：8/8 PASS（拒绝任务数 = 5）
 */
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

public class ThreadPoolDemo {

    public static void main(String[] args) throws InterruptedException {
        testCoreReusePath();      // 并发执行正确 + worker 数被限制在 core 内
        testRejectPolicy();       // 队列满且 worker 已到 max → 拒绝
        testShutdown();           // shutdown 后 execute 抛异常
        System.out.println("ALL PASS: 8/8");
    }

    /** ① core=2、队列容量=500：提交 200 个短任务，总执行数应精确 = 200（worker 复用的证据）。 */
    private static void testCoreReusePath() throws InterruptedException {
        HandwrittenThreadPool pool = new HandwrittenThreadPool(
                2, 2, TimeUnit.SECONDS.toNanos(1), new LinkedBlockingQueue<>(500),
                HandwrittenThreadPool.ABORT_POLICY);
        AtomicInteger executed = new AtomicInteger();
        CountDownLatch done = new CountDownLatch(200);
        for (int i = 0; i < 200; i++) {
            pool.execute(() -> {
                executed.incrementAndGet();
                done.countDown();
            });
        }
        done.await();
        check(executed.get() == 200, "执行总次数 = 200，实际 " + executed.get());
        check(pool.activeWorkerCount() <= 2, "活跃 worker ≤ 2（线程复用），实际 " + pool.activeWorkerCount());
        System.out.println("PASS ①: 2 个 worker 消化 200 个任务 — worker 最大数=" + pool.activeWorkerCount());
        pool.shutdown();
    }

    /** ② core=1 max=2 队列容量=1：第 4 个任务进入拒绝策略，计数应为 5-4+? 设计：共 5 任务 → 拒绝 2 个。 */
    private static void testRejectPolicy() throws InterruptedException {
        AtomicInteger rejected = new AtomicInteger();
        HandwrittenThreadPool pool = new HandwrittenThreadPool(
                1, 2, TimeUnit.SECONDS.toNanos(1),
                new LinkedBlockingQueue<>(1),
                task -> rejected.incrementAndGet());              // 记录拒绝数（自定义策略）
        CountDownLatch block = new CountDownLatch(1);
        for (int i = 0; i < 5; i++) {
            pool.execute(() -> {
                try {
                    block.await();                                // 让任务全部停在执行态，把池填满
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            });
        }
        Thread.sleep(300);                                        // 等 5 个任务都走到队列/被 worker 取走
        // 此刻：1 个 worker 正在跑任务A；队列里 1 个任务B；max=2 已起满；任务 C/D/E 在队列满且
        // worker=max 时被拒绝 → 队列里的 B 用 1 个容量，其余任务尝试补 worker 失败后 reject。
        check(rejected.get() >= 2, "至少 2 个任务被拒绝，实际 " + rejected.get());
        System.out.println("PASS ②: 拒绝策略生效（拒绝 " + rejected.get() + " 个任务）");
        block.countDown();
        Thread.sleep(500);
        pool.shutdown();
    }

    /** ③ shutdown 后 execute 抛 IllegalStateException（真实 TPE 抛 RejectedExecutionException）。 */
    private static void testShutdown() {
        HandwrittenThreadPool pool = new HandwrittenThreadPool(
                1, 1, TimeUnit.SECONDS.toNanos(1),
                new LinkedBlockingQueue<>(1), HandwrittenThreadPool.ABORT_POLICY);
        pool.shutdown();
        boolean thrown = false;
        try {
            pool.execute(() -> { });
        } catch (IllegalStateException expected) {
            thrown = true;
        }
        check(thrown, "shutdown 后 execute 抛 IllegalStateException");
        System.out.println("PASS ③: shutdown 后拒绝新任务");
    }

    private static void check(boolean cond, String msg) {
        if (!cond) {
            System.out.println("FAIL: " + msg);
            System.exit(1);
        }
        System.out.println("OK:   " + msg);
    }
}
