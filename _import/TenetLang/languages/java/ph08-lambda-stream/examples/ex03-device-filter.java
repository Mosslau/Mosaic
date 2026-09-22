// examples/ex03-device-filter.java —— 设备状态筛选：Predicate 组合 + Optional 处理缺失
// 对应主文档 6. 示例 3：Predicate.and 组合条件，findFirst + Optional 处理「查无设备」
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex03-device-filter.java
// 运行：java DeviceFilter（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
import java.util.*;
import java.util.function.*;
import java.util.stream.*;

class DeviceFilter {
    public static void main(String[] args) {
        List<Device> devices = Arrays.asList(
                new Device("d-001", "online", 85), new Device("d-002", "offline", 60),
                new Device("d-003", "online", 30), new Device("d-004", "fault", 95));

        Predicate<Device> isOnline = d -> "online".equals(d.status);
        Predicate<Device> batteryOk = d -> d.battery >= 50;
        List<Device> candidates = devices.stream()
                .filter(isOnline.and(batteryOk))        // Predicate 组合
                .collect(Collectors.toList());
        System.out.println("可调度设备: " + candidates);

        Optional<Device> found = devices.stream()
                .filter(d -> d.id.equals("d-999"))
                .findFirst();
        Device result = found.orElse(new Device("unknown", "offline", 0));  // 兜底默认对象
        System.out.println("查找 d-999: " + result);

        int battery = devices.stream()
                .filter(d -> d.id.equals("d-001"))
                .findFirst()
                .map(d -> d.battery)                    // 链式：存在才转换
                .orElseThrow(() -> new IllegalStateException("设备 d-001 不存在"));
        System.out.println("d-001 电量: " + battery);
    }

    // 教学简化：为聚焦 Stream 主题，字段未做封装（省略 private + getter）
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
