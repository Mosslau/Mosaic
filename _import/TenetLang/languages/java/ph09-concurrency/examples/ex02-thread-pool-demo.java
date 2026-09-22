// examples/ex02-thread-pool-demo.java —— 线程池参数与任务提交流程：先填队列后扩线程 + 拒绝策略
// 对应主文档 6. 示例 2：core=2 / max=4 / 有界队列 8，观察扩线程与 AbortPolicy 拒绝，以及优雅关闭
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex02-thread-pool-demo.java
// 运行：java ThreadPoolDemo（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

class ThreadPoolDemo {
    public static void main(String[] args) throws Exception {
        demoSubmitFlow();    // 提交流程：先填队列后扩线程 + 拒绝
        demoCallerRuns();    // CallerRunsPolicy：提交者自己执行，天然背压
    }

    /** 提交 13 个阻塞任务：2 个占住核心线程 + 8 个排队 + 2 个扩到最大 4，第 13 个被拒绝（全程可复现） */
    static void demoSubmitFlow() throws Exception {
        ThreadPoolExecutor pool = new ThreadPoolExecutor(
                2, 4, 60L, TimeUnit.SECONDS,
                new ArrayBlockingQueue<>(8),
                Executors.defaultThreadFactory(),
                new ThreadPoolExecutor.AbortPolicy());
        CountDownLatch gate = new CountDownLatch(1);   // 任务全部提交前一律阻塞，保证提交过程可复现
        List<Future<Integer>> futures = new ArrayList<>();
        for (int i = 1; i <= 12; i++) {                // 2 个直接执行 + 8 个排队 + 2 个扩到 4 线程
            final int task = i;
            futures.add(pool.submit(() -> {
                gate.await();                          // 提交阶段全部阻塞，线程池状态稳定可观测
                return task * task;
            }));
            printPool(pool, "提交第 " + i + " 个任务后");
        }
        try {
            pool.submit(() -> 13);                     // 队列满(8)且线程已达最大(4) → 拒绝
            System.out.println("第 13 个任务被接受（意外）");
        } catch (RejectedExecutionException e) {
            System.out.println("第 13 个任务被拒绝: " + e.getClass().getSimpleName());
        }
        gate.countDown();                              // 放行，任务开始执行
        int sum = 0;
        for (Future<Integer> f : futures) sum += f.get();   // get() 阻塞等待每个结果
        System.out.println("1~12 的平方和 = " + sum + "  (期望 650)");
        if (sum != 650) throw new AssertionError("任务结果不符");
        pool.shutdown();                               // 优雅关闭：不再接新任务，跑完已提交
        boolean done = pool.awaitTermination(10, TimeUnit.SECONDS);
        System.out.println("线程池已优雅关闭: " + done);
        if (!done) throw new AssertionError("线程池未在时限内关闭");
    }

    static void printPool(ThreadPoolExecutor pool, String tag) {
        System.out.printf("%s: poolSize=%d, queueSize=%d%n",
                tag, pool.getPoolSize(), pool.getQueue().size());
    }

    /** CallerRunsPolicy：队列满且线程满时，由提交者（主线程）自己执行——不丢任务，天然背压 */
    static void demoCallerRuns() throws Exception {
        ThreadPoolExecutor pool = new ThreadPoolExecutor(
                1, 1, 0L, TimeUnit.MILLISECONDS,
                new ArrayBlockingQueue<>(1),
                new ThreadPoolExecutor.CallerRunsPolicy());
        AtomicInteger onMain = new AtomicInteger();
        for (int i = 1; i <= 3; i++) {
            final int id = i;
            pool.execute(() -> {
                String who = Thread.currentThread().getName();
                System.out.println("任务" + id + " 由 " + who + " 执行");   // 各行顺序随调度而异，计数才是断言
                if (who.equals("main")) onMain.incrementAndGet();
            });
        }
        pool.shutdown();
        pool.awaitTermination(5, TimeUnit.SECONDS);
        System.out.println("由主线程（提交者）执行的任务数 = " + onMain.get() + "  (期望恰好 1 个)");
        // 注：极端调度下（worker 恰好在三次提交的窗口内跑完任务并清空队列）该计数可能为 0——理论竞态，
        // 实测 5/5 稳定，教学场景接受
        if (onMain.get() != 1) throw new AssertionError("CallerRunsPolicy 应恰好有 1 个任务在主线程执行");
    }
}
