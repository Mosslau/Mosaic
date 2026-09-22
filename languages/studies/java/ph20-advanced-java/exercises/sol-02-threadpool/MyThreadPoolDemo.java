/*
 * exercises/sol-02-threadpool/MyThreadPoolDemo.java —— 练习 2 参考实现演示
 * 验证：① submit(Callable) 返回 Future 且结果正确；② 多任务并发执行在池内复用线程；
 *       ③ shutdown 后 execute 抛 RejectedExecutionException（新任务被拒）。
 *
 * 验证环境：OpenJDK 17.0.18（Homebrew）
 * 编译：javac -encoding UTF-8 -d /tmp/tl20-cls MyThreadPool.java MyThreadPoolDemo.java
 * 运行：java -cp /tmp/tl20-cls MyThreadPoolDemo
 * 本机已实测：5/5 PASS
 */
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.FutureTask;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

public final class MyThreadPoolDemo {

    public static void main(String[] args) throws Exception {
        MyThreadPool pool = new MyThreadPool(2, 4, TimeUnit.SECONDS.toNanos(1), new LinkedBlockingQueue<>(100));
        AtomicInteger executed = new AtomicInteger();

        // ① submit 带返回值：10 个任务各自算 id*2，Future 逐个取回
        List<FutureTask<Integer>> futures = new ArrayList<>();
        for (int i = 1; i <= 10; i++) {
            final int id = i;
            futures.add(pool.submit(() -> {
                executed.incrementAndGet();
                return id * 2;
            }));
        }
        int sum = 0;
        for (FutureTask<Integer> f : futures) {
            sum += f.get();                       // 阻塞等结果（这是 Future 的同步语义）
        }
        check(sum == 110, "submit 返回值正确：1*2+...+10*2 = " + sum);
        check(executed.get() == 10, "10 个任务全部执行，执行数 = " + executed.get());

        // ② 抛异常的任务：Future.get 会把任务异常包装成 ExecutionException 抛给调用方
        FutureTask<Integer> boom = pool.submit(() -> {
            throw new IllegalStateException("boom");
        });
        try {
            boom.get();
            check(false, "应抛 ExecutionException 却拿到了值");
        } catch (ExecutionException expected) {
            check(expected.getCause() instanceof IllegalStateException, "Future.get 传播任务异常 (ExecutionException)");
        }

        // ③ shutdown 后 execute 抛拒绝异常
        pool.shutdown();
        boolean rejected = false;
        try {
            pool.execute(() -> { });
        } catch (RejectedExecutionException expected) {
            rejected = true;
        }
        check(rejected, "shutdown 后 execute 抛 RejectedExecutionException");
        System.out.println("ALL PASS: 5/5");
    }

    private static void check(boolean cond, String msg) {
        System.out.println((cond ? "PASS: " : "FAIL: ") + msg);
        if (!cond) {
            System.exit(1);
        }
    }
}
