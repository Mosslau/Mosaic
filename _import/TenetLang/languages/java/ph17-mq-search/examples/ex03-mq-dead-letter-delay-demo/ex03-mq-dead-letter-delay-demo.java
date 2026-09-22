// examples/ex03-mq-dead-letter-delay-demo/ex03-mq-dead-letter-delay-demo.java
// 死信队列 + 延迟消息的纯 Java 语义模拟（对应主文档 3.6 的能力表）
// 教学映射：本文件模拟的「重试 → 死信」对应 Kafka .dlt / RocketMQ %DLQ% / RabbitMQ DLX；
//           「availableAt 到期才投递」对应 RocketMQ 18 级延迟消息 / RabbitMQ TTL+DLX / Kafka 分层重试 topic
// 设计：用「虚拟时钟」驱动全部时间判断（不 sleep、不依赖真实时间），两次场景的断言结果确定可复现。
// 验证环境：OpenJDK 17（javac -version -> 17.x）；无第三方依赖
// 验证命令：
//   # 1. 编译（文件在 examples/ex03-mq-dead-letter-delay-demo/ 目录下执行）
//   javac ex03-mq-dead-letter-delay-demo.java
//   # 2. 运行（主类名与文件名不一致是刻意为之：单一文件 + 非 public 类的协调，参照 ph09 示例约定）
//   java DeadLetterDelayDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：javac 编译通过、运行全部 PASS）

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.PriorityQueue;

/** 死信 + 延迟消息演示：虚拟时钟 broker + 失败重试 + 死信队列 */
final class DeadLetterDelayDemo {

    /** 一条消息：availableAt <= broker.clock 才可投递（延迟消息 = availableAt 在未来） */
    static final class Msg {
        final long id;
        final String bizKey;
        final String payload;
        int attempt;          // 已尝试次数（0 起）
        long availableAt;     // 虚拟时间戳：最早可投递时刻

        Msg(long id, String bizKey, String payload, long availableAt) {
            this.id = id;
            this.bizKey = bizKey;
            this.payload = payload;
            this.availableAt = availableAt;
        }

        @Override
        public String toString() {
            return "Msg#" + id + "(" + bizKey + ", attempt=" + attempt + ", due=" + availableAt + ")";
        }
    }

    /** 模拟 broker：一个到期队列 + 一个死信队列，全部按虚拟时钟调度 */
    static final class Broker {
        private final PriorityQueue<Msg> queue =
                new PriorityQueue<>(Comparator.comparingLong(m -> m.availableAt));
        private final List<Msg> dlq = new ArrayList<>();
        long clock = 0;

        /** 投递（生产者）：未到期的自动在队列里等；到期时间早的排前面 */
        void send(Msg m) {
            queue.offer(m);
        }

        /** 拉取（消费者）：只给「已到期」的消息，没有就返回 null */
        Msg poll() {
            Msg top = queue.peek();
            if (top != null && top.availableAt <= clock) {
                return queue.poll();
            }
            return null;
        }

        /** 推进虚拟时钟（模拟时间流逝） */
        void tickTo(long target) {
            if (target > clock) {
                clock = target;
            }
        }

        void sendToDlq(Msg m) {
            dlq.add(m);
        }

        int dlqSize() {
            return dlq.size();
        }
    }

    /** 消费者对单条消息的处理结果 */
    interface Handler {
        /** 返回 true = 处理成功；false = 处理失败（需要重试/进死信） */
        boolean handle(Msg m);
    }

    /**
     * 消费到「队列空且无到期消息」为止：失败消息若没到上限，延迟 retryDelay 后重新投递（重试 topic 语义）；
     * 到上限进死信队列。返回本回合实际处理条数。
     */
    static int drain(Broker broker, Handler handler, int maxAttempts, long retryDelay) {
        int processed = 0;
        Msg m;
        while ((m = broker.poll()) != null) {
            processed++;
            if (handler.handle(m)) {
                System.out.println("  ok      " + m);
                continue;
            }
            m.attempt++;
            if (m.attempt < maxAttempts) {
                m.availableAt = broker.clock + retryDelay; // 延迟重投：下次到期才可见（对应重试 topic）
                broker.send(m);
                System.out.println("  retry   " + m + "（" + retryDelay + " 个虚拟时间单位后重投）");
            } else {
                broker.sendToDlq(m);
                System.out.println("  DEAD    " + m + "（已达上限，进死信队列）");
            }
        }
        return processed;
    }

    static void check(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError("自检失败: " + label);
        }
        System.out.println("PASS  " + label);
    }

    public static void main(String[] args) {
        System.out.println("场景一：处理恒失败 -> 重试 2 次后进死信队列（maxAttempts=3, retryDelay=10）");
        Broker broker = new Broker();
        Msg alwaysFail = new Msg(1, "alarm-1", "下游 5xx", broker.clock);
        broker.send(alwaysFail);
        drain(broker, m -> false, 3, 10);   // clock=0：第 1 次失败 -> attempt=1, due=10
        broker.tickTo(10);
        drain(broker, m -> false, 3, 10);   // 第 2 次失败 -> attempt=2, due=20
        broker.tickTo(20);
        drain(broker, m -> false, 3, 10);   // 第 3 次失败 -> attempt=3 == maxAttempts -> DLQ
        check(alwaysFail.attempt == 3, "恒失败消息共尝试 3 次");
        check(broker.dlqSize() == 1, "尝试 3 次后进了死信队列（没有无限重试拖死消费者）");
        check(broker.queue.isEmpty(), "主队列已空（消息不再占着消费者）");

        System.out.println("场景二：延迟消息按到期时间投递（A 先入队但 B 到期更早 -> 按到期先后投递）");
        Broker broker2 = new Broker();
        List<String> order = new ArrayList<>();
        Msg a = new Msg(10, "order-a", "30 秒后关单", broker2.clock + 100); // A 到期晚（100）
        Msg b = new Msg(11, "order-b", "立即处理", broker2.clock + 30);      // B 到期早（30）
        broker2.send(a);
        broker2.send(b);
        // 时间走到 30 之前：A/B 都不可投递
        broker2.tickTo(29);
        check(broker2.poll() == null, "clock=29 时没有消息到期（延迟消息未提前漏投）");
        // 到 30：B 到期先被消费；A 仍不可见
        broker2.tickTo(30);
        order.add("b:" + (broker2.poll() != null));
        check(broker2.poll() == null, "clock=30 时 A 尚未到期（到期时间未到就不投）");
        // 到 100：A 到期
        broker2.tickTo(100);
        order.add("a:" + (broker2.poll() != null));
        check(broker2.poll() == null, "clock=100 消费完 A 后队列为空");
        check(order.equals(List.of("b:true", "a:true")), "投递顺序 = 到期时间顺序（b 先于 a），与入队顺序无关");

        System.out.println("场景三：成功消息不重试不进死信（对照组）");
        Broker broker3 = new Broker();
        Msg good = new Msg(20, "order-ok", "正常业务", broker3.clock);
        broker3.send(good);
        int processed = drain(broker3, m -> true, 3, 10);
        check(processed == 1 && good.attempt == 0 && broker3.dlqSize() == 0,
                "处理成功的消息：处理 1 次、0 次重试、不进死信");

        System.out.println();
        System.out.println("全部自检通过。对照主文档 3.6：");
        System.out.println("  - RocketMQ：失败自动重试默认 16 次后进 %DLQ%消费组；延迟消息原生 18 级");
        System.out.println("  - RabbitMQ：basicNack(requeue=false) 或 TTL 过期 -> 按 x-dead-letter-exchange 转投 DLX");
        System.out.println("  - Kafka：无原生，用重试 topic + .dlt 主题自建（本文件的实现思路即其最小版）");
    }
}
