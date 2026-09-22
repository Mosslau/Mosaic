// examples/ex01-device-management/DeviceManagementDemo.java —— 设备管理主入口：聚合状态机 + 审计事件流
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：
//   javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//   java -cp /tmp/tl21-cls DeviceManagementDemo
// 期望输出：3/3 PASS 行 + 状态机完整迁移序列(审计)。
import java.util.concurrent.atomic.AtomicInteger;

public final class DeviceManagementDemo {
    public static void main(String[] args) {
        InMemoryDeviceRepository repo = new InMemoryDeviceRepository();

        // 1) 注册三台车(两电动乘用车 + 一商用车)
        VehicleDevice v1 = repo.register("LSV0000001", "EV-Sedan", "FW 1.4.0");
        VehicleDevice v2 = repo.register("LSV0000002", "EV-Sedan", "FW 1.4.0");
        VehicleDevice v3 = repo.register("LSV0000003", "EV-Truck", "FW 2.1.0");

        // 2) 生命周期：激活上线 → 收到遥测刷新 → OTA 升级 → 完成
        repo.record(v1.activate("factory-delivery"));
        repo.record(v1.onTelemetry(100, "heartbeat"));

        repo.record(v2.activate("factory-delivery"));
        repo.record(v2.markOffline("tunnel-no-signal"));          // 隧道掉线
        repo.record(v2.onTelemetry(101, "reconnect"));            // 恢复 = 自动回 ONLINE

        repo.record(v3.activate("factory-delivery"));
        repo.record(v3.startOta("campaign-2025-09"));             // 进入 UPDATING
        repo.record(v3.finishOta("FW 2.2.0", "ota-success"));     // 固件升级 + 回 ONLINE

        // 3) 校验三件事
        AtomicInteger pass = new AtomicInteger();
        check(pass, v1.status() == DeviceStatus.ONLINE, "v1 遥测后应 ONLINE");
        check(pass, v2.status() == DeviceStatus.ONLINE && v2.lastTelemetrySeq() == 101,
                "v2 掉线重连后应 ONLINE 且序号推进到 101");
        check(pass, v3.status() == DeviceStatus.ONLINE && "FW 2.2.0".equals(v3.firmwareVersion()),
                "v3 OTA 完成后固件升到 FW 2.2.0 且回 ONLINE");

        // 4) 非法迁移必须被聚合根拦下(而不是漏到 Service)
        boolean rejected = false;
        try {
            v3.retire("scrap");
            v3.markOffline("impossible");      // RETIRED 后还想去 OFFLINE
        } catch (IllegalStateException e) {
            rejected = true;
        }
        check(pass, rejected, "RETIRED 是终态，后续迁移必须抛 IllegalStateException");

        System.out.println("== 审计事件流 ==");
        repo.eventStream().forEach(e -> System.out.println(
                "  " + e.vin() + "  " + String.valueOf(e.from()) + " -> " + e.to() + "  (" + e.reason() + ")"));
        System.out.printf("ALL PASS: %d/%d%n", pass.get(), 4);
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) { pass.incrementAndGet(); }
    }
}
