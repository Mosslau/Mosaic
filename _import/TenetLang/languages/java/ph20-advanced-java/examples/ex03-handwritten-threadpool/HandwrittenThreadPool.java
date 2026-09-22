/*
 * examples/ex03-handwritten-threadpool/HandwrittenThreadPool.java + ThreadPoolDemo.java
 * 参照 ThreadPoolExecutor 的核心执行流程手写一个最小线程池（教学精简版）：
 *   execute(task):
 *     worker 数 < core      → 新建核心 Worker 立即跑
 *     否则任务进阻塞队列    → 排队
 *     队列满且 worker < max → 新建非核心 Worker（带 keepAlive 超时）
 *     队列满且 worker = max → 交给 RejectedExecutionHandler（抛异常策略）
 *   线程复用：Worker 循环从队列 take/poll 取任务，而不是每任务一线程。
 *
 * 完整 ThreadPoolExecutor 还多 ctl 状态机、addWorker 双重检查、shutdown 分级等（主文档 3.4），
 * 这里聚焦「任务 → 核心 → 队列 → 非核心 → 拒绝」这条主链的行为。
 *
 * 验证环境：OpenJDK 17.0.18（Homebrew）
 * 编译：javac -encoding UTF-8 -d /tmp/tl20-cls HandwrittenThreadPool.java ThreadPoolDemo.java
 * 运行：java -cp /tmp/tl20-cls ThreadPoolDemo
 * 本机已实测：8/8 PASS
 */
import java.util.List;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

public final class HandwrittenThreadPool {

    private final int coreSize;
    private final int maxSize;
    private final long keepAliveNanos;
    private final BlockingQueue<Runnable> workQueue;
    private final RejectHandler rejectHandler;

    private final AtomicInteger workerCount = new AtomicInteger();
    private final List<Thread> workers = new CopyOnWriteArrayList<>();  // 跟踪全部 worker 线程（shutdown 用）
    private volatile boolean running = true;               // shutdown 标志（教学简化，未做完整状态机）

    /** 拒绝策略接口：与 ThreadPoolExecutor.RejectedExecutionHandler 同构（策略模式）。 */
    @FunctionalInterface
    public interface RejectHandler {
        void rejected(Runnable task);
    }

    public static final RejectHandler ABORT_POLICY = task -> {
        throw new IllegalStateException("Task rejected: " + task);
    };

    public HandwrittenThreadPool(int coreSize, int maxSize, long keepAliveNanos,
                                 BlockingQueue<Runnable> workQueue, RejectHandler rejectHandler) {
        this.coreSize = coreSize;
        this.maxSize = maxSize;
        this.keepAliveNanos = keepAliveNanos;
        this.workQueue = workQueue;
        this.rejectHandler = rejectHandler;
    }

    public void execute(Runnable task) {
        if (!running) {
            throw new IllegalStateException("pool already shutdown");
        }
        // 1) 核心线程未满：新建 worker，并把本任务作为它的 firstTask 立即执行
        //    （真实 TPE 这里调 addWorker(command, false)，任务是直接交给 worker 而不是先进队列）
        if (workerCount.get() < coreSize && addWorker(task)) {
            return;
        }
        // 2) 核心线程已满：先尝试入队（入队成功即被某个空闲 worker 取走）
        if (workQueue.offer(task)) {
            return;
        }
        // 3) 队列满：尝试补非核心线程（带 keepAlive 的临时 worker）
        if (workerCount.get() < maxSize && addWorker(task)) {
            return;
        }
        // 4) 都满了：执行拒绝策略（与 ThreadPoolExecutor 的第四步一致）
        rejectHandler.rejected(task);
    }

    /** 新建一个 worker 并把 firstTask 直接交给它（若 worker 超过 maxSize 则回滚计数）。 */
    private boolean addWorker(Runnable firstTask) {
        for (; ; ) {
            int wc = workerCount.get();
            if (wc >= maxSize) {
                return false;
            }
            if (workerCount.compareAndSet(wc, wc + 1)) {
                Worker w = new Worker(firstTask);
                Thread t = new Thread(w, "pool-worker");
                w.thread = t;
                workers.add(t);
                t.start();
                return true;
            }
        }
    }

    public void shutdown() {
        running = false;
        // 真实 TPE 的 shutdown 会 interruptIdleWorkers：唤醒阻塞在 take() 的空闲 worker，
        // 否则它们会一直 park 导致 JVM 无法退出（本实现的线程泄漏修复点）。
        for (Thread t : workers) {
            t.interrupt();
        }
    }

    /** 每个 Worker 是一个「不断从队列取任务的循环」——线程复用的本质。 */
    private final class Worker implements Runnable {
        final BlockingQueue<Runnable> queue = workQueue;
        Runnable firstTask;
        Thread thread;

        Worker(Runnable firstTask) {
            this.firstTask = firstTask;
        }

        @Override
        public void run() {
            Runnable task = firstTask;
            firstTask = null;
            try {
                while (task != null || (task = getTask()) != null) {   // 取到任务就执行，取不到则退出
                    try {
                        task.run();
                    } finally {
                        task = null;                                   // 防止长任务线程持有引用
                    }
                }
            } finally {
                workerCount.decrementAndGet();
            }
        }

        private Runnable getTask() {
            if (!running) {
                return null;                                           // 关闭后不再取新任务
            }
            boolean timed = workerCount.get() > coreSize;              // 非核心线程才有 keepAlive
            try {
                return timed
                        ? queue.poll(keepAliveNanos, TimeUnit.NANOSECONDS)
                        : queue.take();
            } catch (InterruptedException e) {
                // shutdown 中断空闲 worker：退出取任务循环（真实 TPE 此处会判断是否需要补员）
                return null;
            }
        }
    }

    public int activeWorkerCount() {
        return workerCount.get();
    }

    public int queueSize() {
        return workQueue.size();
    }
}
