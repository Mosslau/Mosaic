// languages/java/ph23-lakehouse-orchestration/examples/ex05-batch-stream-unified/Event.java —— 事件时间的输入模型：一条带事件时间戳的键值事件（批与流共用同一份口径的输入）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex05 *.java && java -cp /tmp/ph23-ex05 UnifiedPipelineDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）

/**
 * 一条事件：key（如设备/实例 id）、eventTs（**事件时间**，数据里带的时间戳）、value（可聚合的度量）。
 * 批流一体的第一个前提就写在这个 record 里：批与流处理的是**同一种**事件、
 * 用的是**同一个** eventTs（而不是各自的处理时间）——否则「同口径」从输入开始就不成立（4.3）。
 * 构造时校验 eventTs 非负，把「时间倒流」这类脏数据挡在入口，而不是让它流到窗口分配里。
 */
public record Event(String key, long eventTs, double value) {

    public Event {
        if (key == null || key.isBlank()) {
            throw new IllegalArgumentException("事件 key 不能为空");
        }
        if (eventTs < 0) {
            throw new IllegalArgumentException("eventTs 不能为负：" + eventTs);
        }
    }
}
