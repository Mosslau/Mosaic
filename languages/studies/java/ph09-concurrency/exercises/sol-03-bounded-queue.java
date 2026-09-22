// exercises/sol-03-bounded-queue.java —— 练习 3 参考实现：线程安全队列（ReentrantLock + Condition 手写有界队列）
// 验证环境：OpenJDK 17.0.18
// 编译：javac sol-03-bounded-queue.java
// 运行：java BoundedQueueSol（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.ReentrantLock;

class BoundedQueueSol {
    static final int CAPACITY = 4;              // 队列容量
    static final int PRODUCERS = 2;
    static final int CONSUMERS = 3;
    static final int PER_PRODUCER = 20;         // 每生产者产量 → 共 40 件

    public static void main(String[] args) throws Exception {
        BoundedQueue queue = new BoundedQueue(CAPACITY);
        AtomicInteger consumed = new AtomicInteger();
        AtomicInteger sum = new AtomicInteger();
        AtomicBoolean dup = new AtomicBoolean();          // 重复消费标记（线程内只记录，主线程判失败）
        boolean[] seen = new boolean[PRODUCERS * PER_PRODUCER];
        CountDownLatch sentinelsOut = new CountDownLatch(CONSUMERS);   // 等全部消费者退出

        Thread[] producers = new Thread[PRODUCERS];
        for (int p = 0; p < PRODUCERS; p++) {
            final int base = p * PER_PRODUCER;
            producers[p] = new Thread(() -> {
                try {
                    for (int i = 1; i <= PER_PRODUCER; i++) queue.put(base + i);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }, "producer-" + (p + 1));
        }

        Thread[] consumers = new Thread[CONSUMERS];
        for (int c = 0; c < CONSUMERS; c++) {
            consumers[c] = new Thread(() -> {
                try {
                    while (true) {
                        int n = queue.take();             // 队空时在 Condition 上 await 阻塞
                        if (n == -1) break;               // 哨兵：该消费者退出
                        consumed.incrementAndGet();
                        sum.addAndGet(n);
                        if (seen[n - 1]) dup.set(true);   // 已被消费过 → 重复
                        seen[n - 1] = true;
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                } finally {
                    sentinelsOut.countDown();
                }
            }, "consumer-" + (c + 1));
        }

        for (Thread t : consumers) t.start();
        for (Thread t : producers) t.start();
        for (Thread t : producers) t.join();
        // 哨兵必须等全部生产者结束再放：否则消费者提前退出、队列满时无人消费，未完成的生产者会饿死
        for (int c = 0; c < CONSUMERS; c++) queue.put(-1);   // 每消费者一个哨兵
        sentinelsOut.await();                              // 等全部消费者拿到哨兵退出

        int expectSum = 40 * 41 / 2;                       // 1+2+...+40 = 820
        System.out.println("总消费数 = " + consumed.get() + "  (期望 40)");
        System.out.println("消费值之和 = " + sum.get() + "  (期望 820)");
        if (consumed.get() != 40 || sum.get() != expectSum || dup.get()) {
            throw new AssertionError("有丢失/重复/重复消费: consumed=" + consumed.get()
                    + ", sum=" + sum.get() + ", dup=" + dup.get());
        }
        for (int i = 0; i < seen.length; i++) {
            if (!seen[i]) throw new AssertionError("丢失: " + (i + 1));
        }
        System.out.println("自检通过：40 件全部消费一次，无丢失无重复");
    }

    /** 自实现有界队列：ReentrantLock + 两个 Condition（notFull / notEmpty），await 一律 while 检查条件 */
    static class BoundedQueue {
        private final int[] items;
        private int head, tail, size;
        private final ReentrantLock lock = new ReentrantLock();
        private final Condition notFull = lock.newCondition();    // 生产者等「不满」
        private final Condition notEmpty = lock.newCondition();   // 消费者等「不空」

        BoundedQueue(int capacity) { items = new int[capacity]; }

        void put(int v) throws InterruptedException {
            lock.lockInterruptibly();
            try {
                while (size == items.length) notFull.await();     // while 而非 if：防虚假唤醒
                items[tail] = v;
                tail = (tail + 1) % items.length;
                size++;
                notEmpty.signal();                                // 唤醒一个消费者
            } finally {
                lock.unlock();                                    // 必须 finally 解锁
            }
        }

        int take() throws InterruptedException {
            lock.lockInterruptibly();
            try {
                while (size == 0) notEmpty.await();
                int v = items[head];
                head = (head + 1) % items.length;
                size--;
                notFull.signal();                                 // 唤醒一个生产者
                return v;
            } finally {
                lock.unlock();
            }
        }
    }
}
