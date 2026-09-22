// examples/ex01-device-management/DeviceEvent.java —— 设备生命周期事件(不可变 record)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
import java.time.Instant;

/** 聚合根每次状态迁移都产出的事件，事件流即审计轨迹。 */
record DeviceEvent(String vin, DeviceStatus from, DeviceStatus to, Instant at, String reason) {
    static DeviceEvent of(String vin, DeviceStatus from, DeviceStatus to, String reason) {
        return new DeviceEvent(vin, from, to, Instant.now(), reason);
    }
}
