// project/src/vehicleiot/DeviceRegistry.java —— 设备管理域：车辆档案 + 在线状态
package vehicleiot;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令(在 project/ 目录)：
//   javac -encoding UTF-8 -d /tmp/tl21-proj src/vehicleiot/*.java
//   java -cp /tmp/tl21-proj vehicleiot.VehicleIotPlatformDemo
//
// DDD 战术设计落点：Vehicle 是聚合根记录(不可变档案 + 状态整体替换)，
// Registry 是仓储与查询边界——不暴露可变内部状态，所有变更走方法并校验状态机。
import java.util.List;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

public final class DeviceRegistry {
    public enum Status { REGISTERED, ONLINE, UPDATING, OFFLINE, RETIRED }

    /** 车辆聚合档案：状态迁移只允许经 Registry 方法(简单状态机：RETIRED 为终态)。 */
    public record Vehicle(String vin, String model, String fwVersion, Status status) { }

    private final ConcurrentHashMap<String, Vehicle> vehicles = new ConcurrentHashMap<>();

    /** 注册新车(重复 VIN 抛异常)。 */
    public Vehicle register(String vin, String model, String fwVersion) {
        Vehicle created = new Vehicle(vin, model, fwVersion, Status.REGISTERED);
        if (vehicles.putIfAbsent(vin, created) != null) {
            throw new IllegalArgumentException("车辆已注册: " + vin);
        }
        return created;
    }

    /** 状态迁移：RETIRED 终态不可复活。 */
    public Vehicle changeStatus(String vin, Status target) {
        Vehicle cur = require(vin);
        if (cur.status() == Status.RETIRED) {
            throw new IllegalStateException("RETIRED 是终态: " + vin);
        }
        Vehicle next = new Vehicle(cur.vin(), cur.model(), cur.fwVersion(), target);
        vehicles.replace(vin, cur, next);     // CAS 防并发覆盖他人更新
        return next;
    }

    /** 遥测上报侧简化：收到帧即视为在线；恢复固件版本接口给 OTA 用。 */
    public Vehicle markOnline(String vin) {
        Vehicle cur = require(vin);
        Vehicle next = new Vehicle(cur.vin(), cur.model(), cur.fwVersion(), Status.ONLINE);
        vehicles.replace(vin, cur, next);
        return next;
    }

    public Vehicle upgradeFirmware(String vin, String newFw) {
        Vehicle cur = require(vin);
        Vehicle next = new Vehicle(cur.vin(), cur.model(), newFw, cur.status());
        vehicles.replace(vin, cur, next);
        return next;
    }

    private Vehicle require(String vin) {
        Vehicle cur = vehicles.get(vin);
        if (cur == null) {
            throw new IllegalArgumentException("车辆不存在: " + vin);
        }
        return cur;
    }

    public Optional<Vehicle> findByVin(String vin)       { return Optional.ofNullable(vehicles.get(vin)); }
    public long countByStatus(Status s) {
        return vehicles.values().stream().filter(v -> v.status() == s).count();
    }
    public List<Vehicle> all() {
        return vehicles.values().stream().sorted((a, b) -> a.vin().compareTo(b.vin())).toList();
    }
    public int size() { return vehicles.size(); }
}
