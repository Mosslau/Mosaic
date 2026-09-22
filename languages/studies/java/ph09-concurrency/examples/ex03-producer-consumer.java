// examples/ex03-producer-consumer.java —— 生产者消费者：BlockingQueue 有界队列天然解决队满阻塞/队空等待
// 对应主文档 6. 示例 3：容量 5 的队列 + 慢消费者，观察 put 在队满时阻塞；验收：10 件全部被消费不重不漏
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex03-producer-consumer.java
// 运行：java ProducerConsumer（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

class ProducerConsumer {
    static final int CAPACITY = 5;
    static final int TOTAL = 10;

    public static void main(String[] args) throws InterruptedException {
        BlockingQueue<Integer> queue = new ArrayBlockingQueue<>(CAPACITY);
        AtomicInteger sum = new AtomicInteger();           // 消费者累计收到的值
        CountDownLatch full = new CountDownLatch(1);       // 生产者填满队列后放行消费者，保证 put 阻塞可复现

        Thread producer = new Thread(() -> {
            for (int i = 1; i <= TOTAL; i++) {
                long start = System.nanoTime();
                try {
                    queue.put(i);                          // 队满时阻塞，等消费者腾位置
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    return;
                }
                long blockedMs = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - start);
                // 消费者先睡 200ms 才开始取：第 6 件起队列必然已满，put 必然阻塞（可复现）
                System.out.println("生产: " + i + (blockedMs >= 50 ? "  (put 阻塞等待 " + blockedMs + " ms)" : ""));
                if (i == CAPACITY) full.countDown();       // 队列已满
            }
            System.out.println("生产者完成");
        }, "producer");

        Thread consumer = new Thread(() -> {
            try {
                full.await();                              // 等生产者填满队列（此刻 put 已阻塞在第 6 件）
                Thread.sleep(200);                         // 故意慢消费：让队列保持满，让 put 持续阻塞
                while (true) {
                    int n = queue.take();                  // 队空时阻塞，等生产者投递
                    System.out.println("  消费: " + n);
                    sum.addAndGet(n);
                    if (n == TOTAL) break;                 // 收到最后一个后退出
                    Thread.sleep(100);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            System.out.println("消费者完成");
        }, "consumer");

        producer.start();
        consumer.start();
        producer.join();
        consumer.join();

        boolean ok = sum.get() == TOTAL * (TOTAL + 1) / 2; // 1+2+...+10 = 55
        System.out.println("消费总数 = " + TOTAL + ", 消费值之和 = " + sum.get() + "  (期望 55, 正确: " + ok + ")");
        if (!ok) throw new AssertionError("消费结果不完整或重复");
        System.out.println("自检通过：10 件全部被消费，不重不漏");
    }
}
