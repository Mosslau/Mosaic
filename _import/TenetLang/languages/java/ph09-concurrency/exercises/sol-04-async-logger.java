// exercises/sol-04-async-logger.java —— 练习 4 参考实现：异步日志系统（多线程产日志 → 单后台线程批量落盘）
// 验证环境：OpenJDK 17.0.18
// 编译：javac sol-04-async-logger.java
// 运行：java AsyncLoggerSol（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
// 产物纪律：日志文件写到 /tmp/async-logger-demo.log，运行结束自动删除，不在仓库内残留
import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.atomic.AtomicInteger;

class AsyncLoggerSol {
    static final int PRODUCERS = 3;                 // 生产者线程数
    static final int PER_PRODUCER = 500;            // 每生产者产 500 条 → 共 1500 条
    static final String POISON = "##POISON##";      // 哨兵消息（字面量常量，同一实例）
    static final Path LOG = Path.of("/tmp", "async-logger-demo.log");

    public static void main(String[] args) throws Exception {
        BlockingQueue<String> queue = new ArrayBlockingQueue<>(128);
        AtomicInteger produced = new AtomicInteger();

        // 单后台写线程：drainTo 批量取（减少锁竞争），不足一批时 take 阻塞等待；见哨兵即收尾
        Thread writer = new Thread(() -> {
            try (BufferedWriter out = Files.newBufferedWriter(LOG, StandardCharsets.UTF_8)) {
                List<String> batch = new ArrayList<>();
                while (true) {
                    batch.clear();
                    int n = queue.drainTo(batch, 100);   // 尽力取 100 条
                    if (n == 0) {
                        String msg = queue.take();
                        if (msg == POISON) break;
                        out.write(msg);
                        out.newLine();
                    } else {
                        for (String msg : batch) {
                            if (msg == POISON) return;   // 哨兵在批量中出现：收尾（其前消息已写入）
                            out.write(msg);
                            out.newLine();
                        }
                    }
                }
            } catch (Exception e) {
                throw new RuntimeException("写日志失败", e);
            }
        }, "log-writer");

        // 3 个生产者线程：各产 500 条
        Thread[] producers = new Thread[PRODUCERS];
        for (int p = 0; p < PRODUCERS; p++) {
            final int pid = p;
            producers[p] = new Thread(() -> {
                try {
                    for (int i = 0; i < PER_PRODUCER; i++) {
                        queue.put("producer-" + pid + " message-" + i);
                        produced.incrementAndGet();
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }, "producer-" + pid);
        }

        writer.start();
        for (Thread t : producers) t.start();
        for (Thread t : producers) t.join();       // 等全部生产完成
        queue.put(POISON);                          // 优雅收尾：哨兵保证已入队日志全部落盘，不丢最后几条
        writer.join();                              // 写线程落盘完毕（try-with-resources 已 flush/close）

        List<String> lines = Files.readAllLines(LOG);
        System.out.println("生产总数 = " + produced.get() + "  (期望 " + PRODUCERS * PER_PRODUCER + ")");
        System.out.println("日志行数 = " + lines.size() + "  (期望 " + PRODUCERS * PER_PRODUCER + ", 不丢最后几条)");
        boolean formatOk = lines.stream().allMatch(l -> l.matches("producer-[0-2] message-\\d+"));
        System.out.println("行格式校验 = " + formatOk);
        Files.deleteIfExists(LOG);                  // 清理产物
        if (lines.size() != PRODUCERS * PER_PRODUCER || !formatOk
                || produced.get() != PRODUCERS * PER_PRODUCER) {
            throw new AssertionError("日志丢失或格式错误");
        }
        System.out.println("自检通过：1500 条日志全部落盘，格式正确，产物已清理");
    }
}
