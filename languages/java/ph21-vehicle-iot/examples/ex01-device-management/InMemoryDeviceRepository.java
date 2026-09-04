// examples/ex01-device-management/InMemoryDeviceRepository.java —— 内存仓储(CHM + 事件流)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//
// 并发要点(兑现 ph20 CHM 预告)：用 ConcurrentHashMap 存聚合根，register 用 computeIfAbsent
// 保证「同 VIN 只建一次」是原子的；事件流用 CopyOnWriteArrayList，读多写少无锁读。
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

public final class InMemoryDeviceRepository implements DeviceRepository {
    private final ConcurrentHashMap<String, VehicleDevice> devices = new ConcurrentHashMap<>();
    private final List<DeviceEvent> eventStream = new CopyOnWriteArrayList<>();

    /** 注册：并发下同一 VIN 只创建一个聚合根(工厂放仓储里，DDD 常见做法)。 */
    public VehicleDevice register(String vin, String model, String firmware) {
        return devices.computeIfAbsent(vin, k -> {
            VehicleDevice d = new VehicleDevice(k, model, firmware);
            eventStream.add(DeviceEvent.of(vin, null, DeviceStatus.REGISTERED, "registry.register"));
            return d;
        });
    }

    /** 记录一次状态迁移事件(由应用服务在领域方法返回后调用)。 */
    public void record(DeviceEvent e) {
        if (e != null) {
            eventStream.add(e);
        }
    }

    @Override public Optional<VehicleDevice> findByVin(String vin) { return Optional.ofNullable(devices.get(vin)); }
    @Override public void save(VehicleDevice device) { devices.put(device.vin(), device); }
    @Override public int count() { return devices.size(); }
    public List<DeviceEvent> eventStream() { return new ArrayList<>(eventStream); }
}
