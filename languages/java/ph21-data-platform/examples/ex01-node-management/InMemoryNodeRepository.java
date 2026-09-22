// examples/ex01-node-management/InMemoryNodeRepository.java —— 内存仓储(CHM + 事件流)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//
// 并发要点(兑现 ph20 CHM 预告)：用 ConcurrentHashMap 存聚合根，register 用 computeIfAbsent
// 保证「同 SOURCE_ID 只建一次」是原子的；事件流用 CopyOnWriteArrayList，读多写少无锁读。
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

public final class InMemoryNodeRepository implements NodeRepository {
    private final ConcurrentHashMap<String, SourceNode> nodes = new ConcurrentHashMap<>();
    private final List<NodeEvent> eventStream = new CopyOnWriteArrayList<>();

    /** 注册：并发下同一 SOURCE_ID 只创建一个聚合根(工厂放仓储里，DDD 常见做法)。 */
    public SourceNode register(String sourceId, String model, String firmware) {
        return nodes.computeIfAbsent(sourceId, k -> {
            SourceNode d = new SourceNode(k, model, firmware);
            eventStream.add(NodeEvent.of(sourceId, null, NodeStatus.REGISTERED, "registry.register"));
            return d;
        });
    }

    /** 记录一次状态迁移事件(由应用服务在领域方法返回后调用)。 */
    public void record(NodeEvent e) {
        if (e != null) {
            eventStream.add(e);
        }
    }

    @Override public Optional<SourceNode> findByVin(String sourceId) { return Optional.ofNullable(nodes.get(sourceId)); }
    @Override public void save(SourceNode node) { nodes.put(node.sourceId(), node); }
    @Override public int count() { return nodes.size(); }
    public List<NodeEvent> eventStream() { return new ArrayList<>(eventStream); }
}
