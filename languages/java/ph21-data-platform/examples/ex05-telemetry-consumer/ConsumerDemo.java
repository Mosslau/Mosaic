// examples/ex05-telemetry-consumer/ConsumerDemo.java —— Kafka 遥测消费服务演示(离线可测)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：
//   javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//   java -cp /tmp/tl21-cls ConsumerDemo
// 期望：25 条消息首次消费全部处理；模拟「offset 提交丢失、从 0 重放」后，
// 幂等去重让重复消息不再被处理——processedTotal 仍为 25。
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class ConsumerDemo {
    public static void main(String[] args) {
        MiniKafka kafka = new MiniKafka();
        List<TelemetryMessage> batch = new ArrayList<>();
        for (int v = 1; v <= 5; v++) {
            String vin = "LSV" + String.format("%07d", v);
            for (long seq = 1; seq <= 5; seq++) {
                batch.add(new TelemetryMessage(vin, seq, 40 + seq));   // 5 车 × 5 帧 = 25 条
            }
        }
        kafka.produce(batch);

        TelemetryConsumerService consumer = new TelemetryConsumerService(kafka, 0, 7);
        // 阶段 1：正常消费到 log 末尾
        while (consumer.nextOffset() < kafka.logEndOffset()) {
            consumer.pollAndProcess();
        }
        long firstRun = consumer.processedTotal();

        // 阶段 2：模拟崩溃后从 offset=0 重放(至少一次语义下的重复投递)
        consumer.resetTo(0);
        while (consumer.nextOffset() < kafka.logEndOffset()) {
            consumer.pollAndProcess();
        }
        long secondRun = consumer.processedTotal();

        AtomicInteger pass = new AtomicInteger();
        check(pass, firstRun == 25, "首次消费处理 25 条唯一消息");
        check(pass, consumer.nextOffset() == kafka.logEndOffset(), "offset 已推进到 log 末尾=" + kafka.logEndOffset());
        check(pass, secondRun == firstRun, "崩溃重放后幂等去重生效：新增处理为 0，总处理仍 25");
        System.out.println("首次处理=" + firstRun + "，重放后总处理=" + secondRun + "(重复全被去重)");
        System.out.printf("ALL PASS: %d/3%n", pass.get());
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
