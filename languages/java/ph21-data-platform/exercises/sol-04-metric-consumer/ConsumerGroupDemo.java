// exercises/sol-04-metrics-consumer/ConsumerGroupDemo.java —— Kafka 指标消费服务验收演示
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-sol *.java
//   然后 java -cp /tmp/tl21-sol ConsumerGroupDemo
// 场景：300 个数据源 × seq 1..2 = 600 条唯一消息(按 SOURCE_ID 哈希入 4 分区)，其中 200 条故意重复投递；
//   2 个消费 worker 分摊 4 分区并发消费。验收：distinct 处理 = 600、重复被去重、lag 归零。
import java.util.concurrent.atomic.AtomicInteger;

public final class ConsumerGroupDemo {
    private static final int VIN_COUNT = 300;

    public static void main(String[] args) throws InterruptedException {
        MemoryKafka kafka = new MemoryKafka();
        // 生产：600 条唯一 + 200 条重复(重复投递是 Kafka 常态，必须由消费侧幂等兜住)
        int dup = 0;
        for (int v = 1; v <= VIN_COUNT; v++) {
            String sourceId = "LSV" + String.format("%07d", v);
            for (long seq = 1; seq <= 2; seq++) {
                kafka.produce(new MetricMsg(sourceId, seq, 40 + seq));
                if (v % 3 == 0 && seq == 2) {      // 每 3 个数据源重发最后一条
                    kafka.produce(new MetricMsg(sourceId, seq, 40 + seq));
                    dup++;
                }
            }
        }

        ConsumerGroup group = new ConsumerGroup(kafka, /*worker*/ 2);
        group.start();
        // 等待消费完成：轮询 lag(生产 demo 用忙等最多 5s)
        long deadline = System.currentTimeMillis() + 5000;
        while (!group.lagIsZero() && System.currentTimeMillis() < deadline) {
            Thread.sleep(10);
        }
        group.stop();

        AtomicInteger pass = new AtomicInteger();
        check(pass, group.lagIsZero(), "两个消费者分摊 4 分区后全部消费，lag=0");
        check(pass, group.newlyProcessed() == 600, "唯一消息 600 条全部入库(幂等表去重后恰 600)");
        check(pass, group.distinctKeys() == 600, "distinct 键 = 600(重复投递未产生多余处理)");
        check(pass, group.duplicatesSeen() == dup, "重复投递 " + dup + " 条全部被识别为重复而非二次入库");
        System.out.println("新增处理=" + group.newlyProcessed() + "，去重拦截=" + group.duplicatesSeen()
                + "，distinct=" + group.distinctKeys());
        System.out.printf("ALL PASS: %d/4%n", pass.get());
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) { pass.incrementAndGet(); }
    }
}
