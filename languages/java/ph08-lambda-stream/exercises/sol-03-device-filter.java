// exercises/sol-03-device-filter.java —— 练习 3 参考实现：设备状态筛选
// 验证环境：OpenJDK 17.0.18
// 编译：javac sol-03-device-filter.java
// 运行：java DeviceFilterSol（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
import java.util.*;
import java.util.function.*;
import java.util.stream.*;

class DeviceFilterSol {
    public static void main(String[] args) {
        List<Device> devices = Arrays.asList(
                new Device("d-001", "online", 85), new Device("d-002", "offline", 60),
                new Device("d-003", "online", 30), new Device("d-004", "fault", 95));

        // Predicate 组合：在线 且 电量 >= 50
        Predicate<Device> isOnline = d -> "online".equals(d.status);
        Predicate<Device> batteryOk = d -> d.battery >= 50;
        List<Device> candidates = devices.stream()
                .filter(isOnline.and(batteryOk))
                .collect(Collectors.toList());
        System.out.println("可调度设备: " + candidates);

        // 按 id 查找，查不到返回兜底设备
        Optional<Device> found = findById(devices, "d-999");
        Device result = found.orElse(new Device("unknown", "offline", 0));
        System.out.println("查找 d-999: " + result);

        // 按 id 取电量，查不到抛异常（消息含 id）
        int battery = findById(devices, "d-001")
                .map(d -> d.battery)
                .orElseThrow(() -> new IllegalStateException("设备 d-001 不存在"));
        System.out.println("d-001 电量: " + battery);

        // orElse vs orElseGet：orElse 的参数无条件求值，orElseGet 仅空时执行
        Optional<Device> present = findById(devices, "d-002");
        present.orElse(fallback());        // 值存在，仍打印兜底日志
        present.orElseGet(() -> fallback());  // 值存在，不打印兜底日志
    }

    static Optional<Device> findById(List<Device> devices, String id) {
        return devices.stream().filter(d -> d.id.equals(id)).findFirst();
    }

    static Device fallback() {
        System.out.println("  [兜底逻辑被执行]");   // 观察求值时机
        return new Device("unknown", "offline", 0);
    }

    static class Device {
        String id, status;   // status: online / offline / fault
        int battery;         // 0-100
        Device(String id, String status, int battery) {
            this.id = id; this.status = status; this.battery = battery;
        }
        @Override public String toString() {
            return id + "(" + status + ", 电量" + battery + "%)";
        }
    }
}
