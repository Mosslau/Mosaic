// project/task-scheduler.java —— 线程池任务调度器：有界优先级队列 + 自定义线程工厂 + 拒绝告警 + 优雅关闭
// 对应 Roadmap「ph09 多线程与并发阶段」推荐项目「线程池任务调度器」
// 验证环境：OpenJDK 17.0.18
// 编译：javac task-scheduler.java
// 运行：java TaskScheduler（注意是类名不是文件名；无参数运行自测）
// 验证状态：已验证：OpenJDK 17.0.18
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

class TaskScheduler {
    static final int CORE = 2;               // 核心线程数
    static final int MAX = 4;                // 最大线程数
    static final int QUEUE_CAPACITY = 6;     // 有界优先级队列容量
    static final int TOTAL_TASKS = 20;       // 提交任务总数

    public static void main(String[] args) throws Exception {
        AtomicInteger rejected = new AtomicInteger();
        List<Integer> rejectedIds = Collections.synchronizedList(new ArrayList<>());
        List<String> startOrder = Collections.synchronizedList(new ArrayList<>());   // 启动顺序(id:优先级)
        CountDownLatch gate = new CountDownLatch(1);     // 提交阶段全部阻塞，保证流程与顺序可复现

        // 1. 自定义线程工厂：统一命名 scheduler-worker-N（生产可在此设 daemon/优先级/线程组）
        ThreadFactory factory = new ThreadFactory() {
            private final AtomicInteger seq = new AtomicInteger(1);
            @Override
            public Thread newThread(Runnable r) {
                Thread t = new Thread(r, "scheduler-worker-" + seq.getAndIncrement());
                t.setDaemon(false);
                return t;
            }
        };

        // 2. 拒绝策略：打印告警日志并计数，绝不静默丢弃
        RejectedExecutionHandler handler = (r, pool) -> {
            Task task = (Task) r;
            rejected.incrementAndGet();
            rejectedIds.add(task.id);
            System.out.println("[告警] 拒绝任务 id=" + task.id + " (poolSize=" + pool.getPoolSize()
                    + ", queueSize=" + pool.getQueue().size() + ")");
        };

        // 3. 有界优先级队列 + 线程池（参数与提交流程见主文档 3.2 / 4.3）
        ThreadPoolExecutor pool = new ThreadPoolExecutor(
                CORE, MAX, 60L, TimeUnit.SECONDS,
                new BoundedPriorityQueue(QUEUE_CAPACITY),
                factory, handler);

        // 4. 提交 20 个任务：id 1,2 占核心线程；id 3~8 进队列（优先级 2,2,3,3,4,4）；
        //    id 9,10 扩到最大线程；id 11~20 触发拒绝（接受 10 / 拒绝 10，全程可复现）
        List<Task> submitted = new ArrayList<>();
        int[] priorities = {1, 1, 2, 2, 3, 3, 4, 4, 1, 1};
        for (int id = 1; id <= TOTAL_TASKS; id++) {
            int priority = id <= 10 ? priorities[id - 1] : (id % 5 + 1);
            Task task = new Task(id, priority, id, gate, startOrder);
            submitted.add(task);
            pool.execute(task);                  // 拒绝时由 handler 接管，不抛异常
        }
        System.out.println("提交完成: poolSize=" + pool.getPoolSize()
                + ", queueSize=" + pool.getQueue().size() + ", 已拒绝=" + rejected.get());

        // 5. 放行并等待收尾
        gate.countDown();
        pool.shutdown();                         // 优雅关闭：不再接新任务，跑完已提交
        boolean terminated = pool.awaitTermination(10, TimeUnit.SECONDS);
        if (!terminated) {
            pool.shutdownNow();
            throw new AssertionError("任务未在时限内完成");
        }

        // 6. 自测断言（任一失败抛 AssertionError）
        List<Task> accepted = submitted.stream().filter(t -> t.endNano != 0).toList();
        List<Task> byStart = accepted.stream()
                .sorted(Comparator.comparingLong(t -> t.startNano)).toList();
        System.out.println("启动顺序(id:优先级): " + byStart.stream()
                .map(t -> t.id + ":" + t.priority).toList());

        check(accepted.size() == 10, "接受数应为 10，实际 " + accepted.size());
        check(rejected.get() == 10, "拒绝数应为 10，实际 " + rejected.get());
        check(rejectedIds.equals(List.of(11, 12, 13, 14, 15, 16, 17, 18, 19, 20)),
                "被拒绝的应为 id 11~20，实际 " + rejectedIds);
        List<Integer> firstFour = byStart.subList(0, 4).stream().map(t -> t.priority).toList();
        check(firstFour.equals(List.of(1, 1, 1, 1)),
                "前 4 个启动的应为优先级 1（占核心/扩线程的 id 1,2,9,10），实际 " + firstFour);
        List<Integer> queuedStart = byStart.stream().filter(t -> t.id >= 3 && t.id <= 8)
                .map(t -> t.priority).toList();
        check(queuedStart.equals(List.of(2, 2, 3, 3, 4, 4)),
                "队列任务应按优先级 2,2,3,3,4,4 启动，实际 " + queuedStart);
        check(accepted.stream().allMatch(t -> t.workerName != null
                        && t.workerName.startsWith("scheduler-worker-")),
                "工作线程名应统一为 scheduler-worker-N");

        // 7. 统计执行耗时（打印参考，不设硬断言——耗时随机器而异）
        long totalNanos = accepted.stream().mapToLong(t -> t.endNano - t.startNano).sum();
        long avgMs = TimeUnit.NANOSECONDS.toMillis(totalNanos / accepted.size());
        long maxMs = accepted.stream().mapToLong(t -> t.endNano - t.startNano)
                .max().orElse(0) / 1_000_000;
        System.out.println("执行耗时统计(ms): avg=" + avgMs + ", max=" + maxMs + " (业务耗时 20ms)");

        System.out.println("全部自测通过：接受 10 / 拒绝 10，优先级调度顺序正确，线程命名统一，优雅关闭成功");
    }

    static void check(boolean cond, String msg) {
        if (!cond) throw new AssertionError(msg);
    }

    /** 调度任务：id + 优先级（1 最高），同优先级按提交序号先提交先执行 */
    static class Task implements Runnable, Comparable<Task> {
        final int id;
        final int priority;                       // 1 最高，5 最低
        final long seq;                           // 提交序号
        private final CountDownLatch gate;
        private final List<String> startOrder;
        private volatile long startNano;          // 执行线程写、主线程读：volatile 保证可见性（主文档 3.3）
        private volatile long endNano;
        private volatile String workerName;

        Task(int id, int priority, long seq, CountDownLatch gate, List<String> startOrder) {
            this.id = id;
            this.priority = priority;
            this.seq = seq;
            this.gate = gate;
            this.startOrder = startOrder;
        }

        @Override
        public void run() {
            try {
                gate.await();                     // 提交阶段阻塞：让启动顺序完全由队列决定
                workerName = Thread.currentThread().getName();
                startNano = System.nanoTime();
                startOrder.add(id + ":" + priority);
                Thread.sleep(20);                 // 模拟业务耗时 20ms
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } finally {
                endNano = System.nanoTime();
            }
        }

        @Override
        public int compareTo(Task o) {            // 队列按 (优先级升序, 提交序号升序) 出队
            int byPriority = Integer.compare(priority, o.priority);
            return byPriority != 0 ? byPriority : Long.compare(seq, o.seq);
        }
    }

    /**
     * 有界优先级队列：PriorityBlockingQueue 的教学性改造。
     * 原版 PriorityBlockingQueue 无界——直接当线程池队列用会任务堆积直至 OOM（主文档 3.2 的坑）；
     * 这里覆写 offer：容量满时返回 false，让 ThreadPoolExecutor 走「先扩线程 → 再执行拒绝策略」流程。
     */
    static class BoundedPriorityQueue extends PriorityBlockingQueue<Runnable> {
        private final int capacity;

        BoundedPriorityQueue(int capacity) {
            super(capacity);
            this.capacity = capacity;
        }

        @Override
        public boolean offer(Runnable r) {
            synchronized (this) {                 // 与 size 检查构成原子操作，防止并发提交下超容
                return size() < capacity && super.offer(r);
            }
        }
    }
}
