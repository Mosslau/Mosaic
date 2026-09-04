// exercises/sol-02-device-management/FleetManager.java —— 设备管理系统核心(参考实现)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-sol *.java
//
// 题目要求(roadmap §21 练习「设备管理系统」)：
//   - 支持车辆注册、按状态查询、批量状态更新(车队级别操作)；
//   - 具备简单的车辆档案：VIN、车型、状态、固件版本；
//   - 线程安全(运维同事可能并发执行上下线/退网)。
// 参考实现：车辆档案为不可变 record，状态用 volatile 引用整体替换(单一状态字段避免部分更新)。
import java.util.List;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

public final class FleetManager {
    public enum Status { REGISTERED, ONLINE, OFFLINE, UPDATING, RETIRED }

    public record Vehicle(String vin, String model, String firmware, Status status) { }

    private final ConcurrentHashMap<String, Vehicle> vehicles = new ConcurrentHashMap<>();

    /** 注册车辆(重复 VIN 抛异常，注册是档案级操作)。 */
    public Vehicle register(String vin, String model, String firmware) {
        Vehicle created = new Vehicle(vin, model, firmware, Status.REGISTERED);
        Vehicle prev = vehicles.putIfAbsent(vin, created);
        if (prev != null) {
            throw new IllegalArgumentException("车辆已注册: " + vin);
        }
        return created;
    }

    /** 批量注册：演示「车队导入」形态；单个 VIN 冲突则整体中止(快照式检查)。 */
    public void registerAll(List<Vehicle> imports) {
        if (imports.stream().anyMatch(v -> vehicles.containsKey(v.vin()))) {
            throw new IllegalArgumentException("批量导入含已注册 VIN");
        }
        imports.forEach(v -> vehicles.put(v.vin(), v));
    }

    /** 状态迁移：不允许从 RETIRED 复活；从任意非终态状态可迁移(简化版，细粒度状态机见 ex01)。 */
    public Vehicle changeStatus(String vin, Status target) {
        Vehicle cur = vehicles.get(vin);
        if (cur == null) {
            throw new IllegalArgumentException("车辆不存在: " + vin);
        }
        if (cur.status() == Status.RETIRED) {
            throw new IllegalStateException("RETIRED 是终态: " + vin);
        }
        return vehicles.compute(vin, (k, v) -> new Vehicle(v.vin(), v.model(), v.firmware(), target));
    }

    public Optional<Vehicle> findByVin(String vin)          { return Optional.ofNullable(vehicles.get(vin)); }
    public long countByStatus(Status s) {
        return vehicles.values().stream().filter(v -> v.status() == s).count();
    }
    public List<Vehicle> listByStatus(Status s) {
        return vehicles.values().stream().filter(v -> v.status() == s)
                .sorted((a, b) -> a.vin().compareTo(b.vin())).toList();
    }
    public long fleetSize()                                 { return vehicles.size(); }
}
