// exercises/sol-02-device-management/FleetManagerDemo.java —— 设备管理系统验收演示
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-sol *.java
//   然后 java -cp /tmp/tl21-sol FleetManagerDemo
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class FleetManagerDemo {
    public static void main(String[] args) {
        FleetManager fleet = new FleetManager();
        // 1) 批量注册 5 台车
        fleet.registerAll(List.of(
                new FleetManager.Vehicle("LSV0000001", "EV-Sedan", "FW 1.4.0", FleetManager.Status.REGISTERED),
                new FleetManager.Vehicle("LSV0000002", "EV-Sedan", "FW 1.4.0", FleetManager.Status.REGISTERED),
                new FleetManager.Vehicle("LSV0000003", "EV-Sedan", "FW 2.0.0", FleetManager.Status.REGISTERED),
                new FleetManager.Vehicle("LSV0000004", "EV-Truck",  "FW 2.1.0", FleetManager.Status.REGISTERED),
                new FleetManager.Vehicle("LSV0000005", "EV-Truck",  "FW 2.1.0", FleetManager.Status.REGISTERED)));

        AtomicInteger pass = new AtomicInteger();
        check(pass, fleet.fleetSize() == 5, "车队注册 5 台");

        // 2) 批量上下线：3 台上线、1 台进 OTA、1 台离线
        fleet.changeStatus("LSV0000001", FleetManager.Status.ONLINE);
        fleet.changeStatus("LSV0000002", FleetManager.Status.ONLINE);
        fleet.changeStatus("LSV0000003", FleetManager.Status.UPDATING);   // OTA 中
        fleet.changeStatus("LSV0000004", FleetManager.Status.OFFLINE);
        fleet.changeStatus("LSV0000005", FleetManager.Status.ONLINE);

        check(pass, fleet.countByStatus(FleetManager.Status.ONLINE) == 3, "在线 3 台");
        check(pass, fleet.countByStatus(FleetManager.Status.UPDATING) == 1, "OTA 中 1 台");
        check(pass, fleet.countByStatus(FleetManager.Status.OFFLINE) == 1, "离线 1 台");
        check(pass, fleet.listByStatus(FleetManager.Status.ONLINE).stream()
                        .allMatch(v -> v.vin().startsWith("LSV")),
                "按状态查询返回全部在线车辆且档案完整");

        // 3) 非法操作拦截：退役后不得复活；未注册 VIN 不得操作
        boolean[] guarded = {false, false};
        try {
            fleet.changeStatus("LSV0000001", FleetManager.Status.RETIRED);
            fleet.changeStatus("LSV0000001", FleetManager.Status.ONLINE);     // 复活 → 拒
        } catch (IllegalStateException e) {
            guarded[0] = true;
        }
        try {
            fleet.changeStatus("LSV9999999", FleetManager.Status.ONLINE);    // 不存在 → 拒
        } catch (IllegalArgumentException e) {
            guarded[1] = true;
        }
        check(pass, guarded[0] && guarded[1], "终态复活与操作未注册 VIN 均被拦截");

        System.out.println("当前车队: " + fleet.fleetSize() + " 台，在线 " + fleet.countByStatus(FleetManager.Status.ONLINE));
        System.out.printf("ALL PASS: %d/6%n", pass.get());
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) { pass.incrementAndGet(); }
    }
}
