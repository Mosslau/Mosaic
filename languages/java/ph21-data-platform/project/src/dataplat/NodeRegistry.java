// project/src/dataplat/NodeRegistry.java —— 节点管理域：数据源档案 + 在线状态
package dataplat;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令(在 project/ 目录)：
//   javac -encoding UTF-8 -d /tmp/tl21-proj src/dataplat/*.java
//   java -cp /tmp/tl21-proj dataplat.DataPlatformDemo
//
// DDD 战术设计落点：Source 是聚合根记录(不可变档案 + 状态整体替换)，
// Registry 是仓储与查询边界——不暴露可变内部状态，所有变更走方法并校验状态机。
import java.util.List;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

public final class NodeRegistry {
    public enum Status { REGISTERED, ONLINE, UPDATING, OFFLINE, RETIRED }

    /** 数据源聚合档案：状态迁移只允许经 Registry 方法(简单状态机：RETIRED 为终态)。 */
    public record Source(String sourceId, String model, String fwVersion, Status status) { }

    private final ConcurrentHashMap<String, Source> vehicles = new ConcurrentHashMap<>();

    /** 注册新数据源(重复 SOURCE_ID 抛异常)。 */
    public Source register(String sourceId, String model, String fwVersion) {
        Source created = new Source(sourceId, model, fwVersion, Status.REGISTERED);
        if (vehicles.putIfAbsent(sourceId, created) != null) {
            throw new IllegalArgumentException("数据源已注册: " + sourceId);
        }
        return created;
    }

    /** 状态迁移：RETIRED 终态不可复活。 */
    public Source changeStatus(String sourceId, Status target) {
        Source cur = require(sourceId);
        if (cur.status() == Status.RETIRED) {
            throw new IllegalStateException("RETIRED 是终态: " + sourceId);
        }
        Source next = new Source(cur.sourceId(), cur.model(), cur.fwVersion(), target);
        vehicles.replace(sourceId, cur, next);     // CAS 防并发覆盖他人更新
        return next;
    }

    /** 指标上报侧简化：收到帧即视为在线；恢复FW 版本版本接口给 版本发布 用。 */
    public Source markOnline(String sourceId) {
        Source cur = require(sourceId);
        Source next = new Source(cur.sourceId(), cur.model(), cur.fwVersion(), Status.ONLINE);
        vehicles.replace(sourceId, cur, next);
        return next;
    }

    public Source upgradeFirmware(String sourceId, String newFw) {
        Source cur = require(sourceId);
        Source next = new Source(cur.sourceId(), cur.model(), newFw, cur.status());
        vehicles.replace(sourceId, cur, next);
        return next;
    }

    private Source require(String sourceId) {
        Source cur = vehicles.get(sourceId);
        if (cur == null) {
            throw new IllegalArgumentException("数据源不存在: " + sourceId);
        }
        return cur;
    }

    public Optional<Source> findByVin(String sourceId)       { return Optional.ofNullable(vehicles.get(sourceId)); }
    public long countByStatus(Status s) {
        return vehicles.values().stream().filter(v -> v.status() == s).count();
    }
    public List<Source> all() {
        return vehicles.values().stream().sorted((a, b) -> a.sourceId().compareTo(b.sourceId())).toList();
    }
    public int size() { return vehicles.size(); }
}
