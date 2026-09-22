// examples/ex02-fake-source-ingest/IngestService.java —— 接入服务：按 SOURCE_ID 分片的有界队列 + 单消费者保序
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//
// 教学点（兑现 ph20 线程池/JMM 预告 + 数据平台数据链路的核心纪律）：
//   「同一个g的帧必须有序」决定了接入层不能用「多个 worker 抢一条队」——那会并发乱序，
//   把稍晚到达的低 seq 帧误判成重复。正确形态是**按 SOURCE_ID 哈希路由到 lane**：
//   每个 lane 一条有界队列 + 一个消费者线程，同 SOURCE_ID 永远进同一 lane → 帧内严格 FIFO，
//   多 SOURCE_ID 之间又能并行消费(与 Kafka 按 key 分区、Netty 连接绑定 EventLoop 同一哲学)。
//
//   1. lane 队列有界：生产(采集端线程)与消费解耦，队满 = 该 lane 过载，丢弃并计数(背压)；
//   2. 每 lane 一个常驻线程：同 SOURCE_ID 顺序处理，去重逻辑因此只需比较「上一条 seq」；
//   3. 坏帧在解析层就拦下：格式/量程非法直接 rejected，不污染下游。
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.atomic.AtomicLong;

public final class IngestService {
    private final Lane[] lanes;
    private final AtomicLong accepted = new AtomicLong();
    private final AtomicLong rejected = new AtomicLong();   // 格式/量程坏帧
    private final AtomicLong duplicates = new AtomicLong(); // 重传/乱序帧(同 SOURCE_ID 内)
    private final AtomicLong backlogDropped = new AtomicLong();  // 队满丢弃(背压)
    private volatile boolean running = true;

    /** lane 内的单消费者：自己的队列 + 每 SOURCE_ID 独立基线，天然无竞争。 */
    private final class Lane implements Runnable {
        private final ArrayBlockingQueue<String> queue;
        private final Thread thread = new Thread(this, "ingest-lane");
        private final java.util.HashMap<String, Long> lastSeqByVin = new java.util.HashMap<>();

        Lane(int capacity) {
            this.queue = new ArrayBlockingQueue<>(capacity);
        }

        void start() { thread.start(); }

        boolean offer(String raw) {
            if (!queue.offer(raw)) {
                return false;               // 队满：调用方记 drop
            }
            return true;
        }

        @Override public void run() {
            while (running || !queue.isEmpty()) {
                String raw = poll();
                if (raw == null) {
                    continue;
                }
                process(raw);
            }
        }

        private String poll() {
            try {
                return queue.poll(200, java.util.concurrent.TimeUnit.MILLISECONDS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return null;
            }
        }

        private void process(String raw) {
            MetricFrame frame = FrameCodec.decode(raw).orElse(null);
            if (frame == null) {
                rejected.incrementAndGet();
                return;
            }
            // 单线程、per-SOURCE_ID 独立序号：同一数据源帧即使被其它数据源的帧隔开，判重也不受干扰
            long last = lastSeqByVin.getOrDefault(frame.sourceId(), -1L);
            if (frame.seq() <= last) {
                duplicates.incrementAndGet();   // 重传/乱序：丢弃
                return;
            }
            lastSeqByVin.put(frame.sourceId(), frame.seq());
            accepted.incrementAndGet();
            maybePublish(frame);                // 真实系统这里写 Kafka(见 ex05)
        }
    }

    public IngestService(int laneCount, int queueCapacityPerLane) {
        this.lanes = new Lane[laneCount];
        for (int i = 0; i < laneCount; i++) {
            lanes[i] = new Lane(queueCapacityPerLane);
        }
    }

    /** 启动全部 lane 消费者(每个 lane 恰一个线程，总量小，常驻)。 */
    public void start() {
        for (Lane lane : lanes) {
            lane.start();
        }
    }

    /** 采集端线程调用：先按 SOURCE_ID 哈希选 lane，再尝试入队。 */
    public void submit(String rawLine) {
        if (!running) {
            return;
        }
        Lane lane = lanes[Math.floorMod(routeKey(rawLine).hashCode(), lanes.length)];
        if (!lane.offer(rawLine)) {
            backlogDropped.incrementAndGet();   // 队满：丢弃并计数(可接受延迟类指标才这么干)
        }
    }

    /** 提取路由键：正常帧取 SOURCE_ID，坏帧取固定常量(仍会走解析被拒)。 */
    private static String routeKey(String raw) {
        int bar = raw.indexOf('|');
        int bar2 = bar < 0 ? -1 : raw.indexOf('|', bar + 1);
        return bar2 > bar ? raw.substring(bar + 1, bar2) : "";
    }

    public void shutdown() {
        running = false;
        for (Lane lane : lanes) {
            try {
                lane.thread.join(2000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }

    public long accepted()       { return accepted.get(); }
    public long rejected()       { return rejected.get(); }
    public long duplicates()     { return duplicates.get(); }
    public long backlogDropped() { return backlogDropped.get(); }
    public int laneCount()       { return lanes.length; }

    private static void maybePublish(MetricFrame f) {
        // 真实场景在此序列化并发往 Kafka topic(按 sourceId 做分区键)
    }
}
