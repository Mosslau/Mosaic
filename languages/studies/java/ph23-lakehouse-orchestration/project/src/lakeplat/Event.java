// project/src/lakeplat/Event.java —— 事件：事件时间语义的最小载体
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

/**
 * 一条业务事件（主文档 3.5）。
 *
 * <p>批算与流算处理的是**同一批 record**、**同一套逻辑**——批流一体的目标不是代码复用，
 * 而是语义一致：同事件时间、同逻辑、同幂等写。因此 Event 不区分「批的事件」与「流的事件」。
 *
 * @param eventId     事件 id（确定性自造，如 {@code evt-0001}）
 * @param instanceId  实体（示例里的"实例"）
 * @param eventTime   事件时间（业务发生时间；窗口与水位线都基于它，不用处理时间）
 * @param value       度量值（如耗时毫秒、调用次数）
 * @param region      维度列，用于列级血缘演示
 */
public record Event(String eventId, String instanceId, long eventTime, long value, String region)
        implements Comparable<Event> {

    public Event {
        if (eventId == null || eventId.isBlank()) {
            throw new IllegalArgumentException("事件 id 不能为空");
        }
        if (eventTime < 0) {
            throw new IllegalArgumentException("事件时间不能为负");
        }
    }

    /** 事件所属的时间窗。 */
    public Window window() {
        return Window.of(eventTime);
    }

    @Override
    public int compareTo(Event other) {
        int byTime = Long.compare(eventTime, other.eventTime);
        return byTime != 0 ? byTime : eventId.compareTo(other.eventId);
    }

    @Override
    public String toString() {
        return eventId + "@" + eventTime + "=" + value;
    }
}
