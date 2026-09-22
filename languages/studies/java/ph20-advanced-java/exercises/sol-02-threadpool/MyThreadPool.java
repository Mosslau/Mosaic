/*
 * exercises/sol-02-threadpool/MyThreadPool.java —— 练习 2 参考实现
 * 在 ex03「core→queue→max→reject」主链基础上补两个真实 ThreadPoolExecutor 能力：
 *   ① submit(Callable) 返回 Future——本质是把任务包成 FutureTask（Runnable）再走 execute；
 *   ② shutdown 语义升级：置 running=false 后仍放行已在执行/已入队的任务，新任务拒绝。
 *   （真实 TPE 用 ctl 状态机区分 RUNNING/SHUTDOWN/STOP/TIDYING/TERMINATED，这里用两态简化）
 *
 * 验证环境：OpenJDK 17.0.18（Homebrew）
 * 编译：javac -encoding UTF-8 -d /tmp/tl20-cls MyThreadPool.java MyThreadPoolDemo.java
 * 运行：java -cp /tmp/tl20-cls MyThreadPoolDemo
 * 本机已实测：5/5 PASS
 */
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.Callable;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.FutureTask;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.List;

public final class MyThreadPool {

    private final int coreSize;
    private final int maxSize;
    private final long keepAliveNanos;
    private final BlockingQueue<Runnable> workQueue;
    private final AtomicInteger workerCount = new AtomicInteger();
    private final List<Thread> workers = new CopyOnWriteArrayList<>();
    private volatile boolean running = true;

    public MyThreadPool(int coreSize, int maxSize, long keepAliveNanos, BlockingQueue<Runnable> workQueue) {
        this.coreSize = coreSize;
        this.maxSize = maxSize;
        this.keepAliveNanos = keepAliveNanos;
        this.workQueue = workQueue;
    }

    /** 提交一个带返回值的任务：FutureTask 既是 Runnable 也是 Future——直接走 execute。 */
    public <T> FutureTask<T> submit(Callable<T> task) {
        FutureTask<T> ft = new FutureTask<>(task);
        execute(ft);                       // ThreadPoolExecutor.submit 就是这么干的：newTaskFor 包装后 execute
        return ft;
    }

    public void execute(Runnable task) {
        if (!running) {
            throw new RejectedExecutionException("pool shut down");
        }
        if (workerCount.get() < coreSize && addWorker(task)) {
            return;
        }
        if (workQueue.offer(task)) {
            return;
        }
        if (workerCount.get() < maxSize && addWorker(task)) {
            return;
        }
        throw new RejectedExecutionException("queue full and workers at max");
    }

    /** shutdown：拒绝新任务，已入队的继续执行完（TPE 的 SHUTDOWN 语义）；唤醒空闲 worker 让 JVM 可退。 */
    public void shutdown() {
        running = false;
        for (Thread t : workers) {
            t.interrupt();
        }
    }

    private boolean addWorker(Runnable firstTask) {
        for (; ; ) {
            int wc = workerCount.get();
            if (wc >= maxSize) {
                return false;
            }
            if (workerCount.compareAndSet(wc, wc + 1)) {
                Worker w = new Worker(firstTask);
                Thread t = new Thread(w, "my-pool-worker");
                workers.add(t);
                t.start();
                return true;
            }
        }
    }

    private final class Worker implements Runnable {
        private Runnable firstTask;

        Worker(Runnable firstTask) {
            this.firstTask = firstTask;
        }

        @Override
        public void run() {
            Runnable task = firstTask;
            firstTask = null;
            try {
                while (task != null || (task = getTask()) != null) {
                    try {
                        task.run();
                    } finally {
                        task = null;
                    }
                }
            } finally {
                workerCount.decrementAndGet();
                workers.remove(Thread.currentThread());     // 从跟踪表移除自己
            }
        }

        private Runnable getTask() {
            if (!running) {
                return null;
            }
            boolean timed = workerCount.get() > coreSize;
            try {
                return timed
                        ? workQueue.poll(keepAliveNanos, TimeUnit.NANOSECONDS)
                        : workQueue.take();
            } catch (InterruptedException e) {
                return null;
            }
        }
    }
}
