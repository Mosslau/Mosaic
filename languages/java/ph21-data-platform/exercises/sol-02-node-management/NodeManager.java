// exercises/sol-02-node-management/NodeManager.java —— 节点管理系统核心(参考实现)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-sol *.java
//
// 题目要求(roadmap §21 练习「节点管理系统」)：
//   - 支持数据源注册、按状态查询、批量状态更新(节点集群级别操作)；
//   - 具备简单的数据源档案：SOURCE_ID、数据源类型、状态、版本；
//   - 线程安全(运维同事可能并发执行上下线/退网)。
// 参考实现：数据源档案为不可变 record，状态用 volatile 引用整体替换(单一状态字段避免部分更新)。
import java.util.List;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

public final class NodeManager {
    public enum Status { REGISTERED, ONLINE, OFFLINE, UPDATING, RETIRED }

    public record Source(String sourceId, String model, String firmware, Status status) { }

    private final ConcurrentHashMap<String, Source> vehicles = new ConcurrentHashMap<>();

    /** 注册数据源(重复 SOURCE_ID 抛异常，注册是档案级操作)。 */
    public Source register(String sourceId, String model, String firmware) {
        Source created = new Source(sourceId, model, firmware, Status.REGISTERED);
        Source prev = vehicles.putIfAbsent(sourceId, created);
        if (prev != null) {
            throw new IllegalArgumentException("数据源已注册: " + sourceId);
        }
        return created;
    }

    /** 批量注册：演示「节点集群导入」形态；单个 SOURCE_ID 冲突则整体中止(快照式检查)。 */
    public void registerAll(List<Source> imports) {
        if (imports.stream().anyMatch(v -> vehicles.containsKey(v.sourceId()))) {
            throw new IllegalArgumentException("批量导入含已注册 SOURCE_ID");
        }
        imports.forEach(v -> vehicles.put(v.sourceId(), v));
    }

    /** 状态迁移：不允许从 RETIRED 复活；从任意非终态状态可迁移(简化版，细粒度状态机见 ex01)。 */
    public Source changeStatus(String sourceId, Status target) {
        Source cur = vehicles.get(sourceId);
        if (cur == null) {
            throw new IllegalArgumentException("数据源不存在: " + sourceId);
        }
        if (cur.status() == Status.RETIRED) {
            throw new IllegalStateException("RETIRED 是终态: " + sourceId);
        }
        return vehicles.compute(sourceId, (k, v) -> new Source(v.sourceId(), v.model(), v.firmware(), target));
    }

    public Optional<Source> findByVin(String sourceId)          { return Optional.ofNullable(vehicles.get(sourceId)); }
    public long countByStatus(Status s) {
        return vehicles.values().stream().filter(v -> v.status() == s).count();
    }
    public List<Source> listByStatus(Status s) {
        return vehicles.values().stream().filter(v -> v.status() == s)
                .sorted((a, b) -> a.sourceId().compareTo(b.sourceId())).toList();
    }
    public long fleetSize()                                 { return vehicles.size(); }
}
