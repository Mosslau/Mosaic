// examples/ex01-node-management/NodeEvent.java —— 节点生命周期事件(不可变 record)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
import java.time.Instant;

/** 聚合根每次状态迁移都产出的事件，事件流即审计作业历史。 */
record NodeEvent(String sourceId, NodeStatus from, NodeStatus to, Instant at, String reason) {
    static NodeEvent of(String sourceId, NodeStatus from, NodeStatus to, String reason) {
        return new NodeEvent(sourceId, from, to, Instant.now(), reason);
    }
}
