// exercises/sol-04-telemetry-consumer/ConsumerGroup.java —— 消费组(参考实现)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-sol *.java
//
// 消费组语义：N 个 worker 分摊 P 个分区(每个分区同一时刻只被一个 worker 读)。
// 幂等键集合跨 worker 共享(ConcurrentHashMap.newKeySet)，重放的消息不会二次入库。
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.LongAdder;

public final class ConsumerGroup {
    private final MemoryKafka kafka;
    private final int workerCount;
    private final Set<String> processedKeys = ConcurrentHashMap.newKeySet();   // 共享幂等表
    private final LongAdder newlyProcessed = new LongAdder();
    private final LongAdder duplicatesSeen = new LongAdder();
    private final List<Worker> workers = new ArrayList<>();
    private final long[] committedOffsets = new long[MemoryKafka.PARTITIONS];

    public ConsumerGroup(MemoryKafka kafka, int workerCount) {
        this.kafka = kafka;
        this.workerCount = workerCount;
    }

    /** 平均分配分区给各 worker(生产上由 group coordinator 做，这里用轮询演示)。 */
    public synchronized void start() {
        if (!workers.isEmpty()) {
            return;
        }
        for (int w = 0; w < workerCount; w++) {
            Set<Integer> owned = new HashSet<>();
            for (int p = 0; p < MemoryKafka.PARTITIONS; p++) {
                if (p % workerCount == w) {
                    owned.add(p);
                }
            }
            Worker worker = new Worker(w, owned);
            workers.add(worker);
            new Thread(worker, "consumer-" + w).start();
        }
    }

    public void stop() {
        workers.forEach(Worker::requestStop);
        workers.forEach(w -> { try { w.thread.join(2000); } catch (InterruptedException e) { Thread.currentThread().interrupt(); } });
    }

    /** 消费进度校验用：分区当前可见是否已全部处理完。 */
    public boolean lagIsZero() {
        for (int p = 0; p < MemoryKafka.PARTITIONS; p++) {
            if (committedOffsets[p] < kafka.logEndOffset(p)) {
                return false;
            }
        }
        return true;
    }

    public long newlyProcessed() { return newlyProcessed.sum(); }
    public long duplicatesSeen() { return duplicatesSeen.sum(); }
    public long distinctKeys()   { return processedKeys.size(); }

    private final class Worker implements Runnable {
        private final int id;
        private final Set<Integer> partitions;
        private final long[] nextOffsets = new long[MemoryKafka.PARTITIONS];
        private final Thread thread;
        private volatile boolean running = true;

        Worker(int id, Set<Integer> partitions) {
            this.id = id;
            this.partitions = partitions;
            this.thread = new Thread(this, "consumer-" + id);
        }

        void requestStop() { running = false; }

        @Override public void run() {
            while (running) {
                boolean worked = false;
                for (int p : partitions) {
                    List<TelemetryMsg> batch = kafka.read(p, nextOffsets[p], 8);
                    if (batch.isEmpty()) {
                        continue;
                    }
                    for (TelemetryMsg msg : batch) {
                        if (processedKeys.add(msg.idempotencyKey())) {
                            processMsg(msg);          // 真实系统：更新状态缓存 + 触发规则引擎
                            newlyProcessed.increment();
                        } else {
                            duplicatesSeen.increment();
                        }
                    }
                    nextOffsets[p] += batch.size();
                    committedOffsets[p] = nextOffsets[p];   // 处理完本批再提交(绝不先提交后处理)
                    worked = true;
                }
                if (!worked) {
                    try {
                        Thread.sleep(5);    // 空闲短暂休眠，避免纯自旋烧 CPU(教学演示)
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        return;
                    }
                }
            }
        }

        private void processMsg(TelemetryMsg m) {
            // 占位：落库/触发告警见 examples/ex03、ex04
        }
    }
}
