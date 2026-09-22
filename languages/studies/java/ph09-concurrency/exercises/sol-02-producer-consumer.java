// exercises/sol-02-producer-consumer.java —— 练习 2 参考实现：生产者消费者（2 生产者 + 3 消费者）
// 验证环境：OpenJDK 17.0.18
// 编译：javac sol-02-producer-consumer.java
// 运行：java ProducerConsumerSol（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

class ProducerConsumerSol {
    static final int CAPACITY = 5;          // 有界队列容量
    static final int PRODUCERS = 2;         // 生产者数
    static final int CONSUMERS = 3;         // 消费者数
    static final int PER_PRODUCER = 15;     // 每生产者产量
    static final int TOTAL = PRODUCERS * PER_PRODUCER;   // 30

    public static void main(String[] args) throws Exception {
        BlockingQueue<Integer> queue = new ArrayBlockingQueue<>(CAPACITY);
        AtomicInteger sum = new AtomicInteger();          // 消费值之和
        int[] perConsumer = new int[CONSUMERS];           // 每消费者处理数（主线程汇总）

        // 3 个消费者：收到哨兵 -1 即退出
        Thread[] consumers = new Thread[CONSUMERS];
        for (int c = 0; c < CONSUMERS; c++) {
            final int idx = c;
            consumers[c] = new Thread(() -> {
                int count = 0;
                try {
                    while (true) {
                        int n = queue.take();             // 队空时阻塞
                        if (n == -1) break;               // 哨兵：该消费者退出
                        count++;
                        sum.addAndGet(n);
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
                perConsumer[idx] = count;
            }, "consumer-" + (idx + 1));
        }

        // 2 个生产者：各产 15 件（1..15 / 16..30），只产数据不放哨兵
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

        for (Thread t : consumers) t.start();
        for (Thread t : producers) t.start();
        for (Thread t : producers) t.join();
        // 哨兵必须等全部生产者结束再放：否则消费者提前退出、队列满时无人消费，未完成的生产者会饿死
        for (int c = 0; c < CONSUMERS; c++) queue.put(-1);
        for (Thread t : consumers) t.join();  // 3 个哨兵保证每个消费者都能退出

        int totalConsumed = 0;
        for (int i = 0; i < CONSUMERS; i++) {
            System.out.println("消费者 " + (i + 1) + " 处理 " + perConsumer[i] + " 件");
            totalConsumed += perConsumer[i];
        }
        int expectSum = TOTAL * (TOTAL + 1) / 2;          // 1+2+...+30 = 465
        System.out.println("总消费数 = " + totalConsumed + "  (期望 " + TOTAL + ")");
        System.out.println("消费值之和 = " + sum.get() + "  (期望 " + expectSum + ")");
        if (totalConsumed != TOTAL || sum.get() != expectSum) {
            throw new AssertionError("有消息丢失或重复");
        }
        System.out.println("自检通过：" + TOTAL + " 件全部被消费，不重不漏");
    }
}
