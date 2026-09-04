// project/src/vehicleiot/VehicleIotPlatformDemo.java —— 车联网后台平台(收官项目)端到端演示
package vehicleiot;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令(在 project/ 目录)：
//   javac -encoding UTF-8 -d /tmp/tl21-proj src/vehicleiot/*.java
//   java -cp /tmp/tl21-proj vehicleiot.VehicleIotPlatformDemo
//
// 数据链路(roadmap §21 的「车辆 → 接入 → 总线 → 消费/清洗/告警/存储 → 后台」)：
//
//   3 台模拟车 ──并发──▶ IngestService(校验+去重) ──▶ TelemetryBus(按 VIN 分区)
//        ──▶ TelemetryConsumer.drain ──▶ 状态缓存 + 轨迹 + 设备在线 + 告警引擎
//   OtaPlatform 单独跑一个升级批次(成功/失败/回滚)，最后 OpsConsole 出运维总览。
//
// 全部内存实现、无第三方依赖，验收断言即 PASS 行。每个模块对应一个真实服务边界：
// registry=设备管理服务，ingest=接入网关后的接入服务，bus≈Kafka topic，
// consumer=遥测消费服务，alert=告警引擎，ota=OTA 平台，console=运维后台。
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class VehicleIotPlatformDemo {
    private static final int FRAMES_PER_VEHICLE = 400;

    public static void main(String[] args) throws InterruptedException {
        DeviceRegistry registry = new DeviceRegistry();
        // 注册 6 台车：3 台即将并发上报遥测，3 台留给 OTA 批次
        for (int i = 1; i <= 6; i++) {
            registry.register("LSV" + String.format("%07d", i), MODEL(i), "FW 1.4.0");
        }

        TelemetryBus bus = new TelemetryBus();
        IngestService ingest = new IngestService(bus);

        VehicleStateCache stateCache = new VehicleStateCache();
        TrackStore trackStore = new TrackStore();
        AlertEngine alerts = new AlertEngine(List.of(new AlertRules.LowSocRule(), new AlertRules.OverheatRule()));

        // 三台模拟车并发上报(车 1 末帧低电、车 2 末帧过热，供规则引擎触发)
        List<Thread> cars = new ArrayList<>();
        for (int i = 1; i <= 3; i++) {
            final String vin = "LSV" + String.format("%07d", i);
            final boolean lowSocEnd = (i == 1);
            final boolean overheatEnd = (i == 2);
            Thread t = new Thread(() -> reportCar(vin, ingest, lowSocEnd, overheatEnd), "car-" + vin);
            cars.add(t);
            t.start();
        }
        for (Thread t : cars) {
            t.join();
        }

        // 消费总线积压：一次 drain 处理全部帧
        TelemetryConsumer consumer = new TelemetryConsumer(bus, registry, stateCache, trackStore, alerts);
        long drained = consumer.drain();

        // OTA 批次：发布 2.2.0 并给 4/5/6 号车升级
        OtaPlatform ota = new OtaPlatform();
        OtaPlatform.OtaBatch batch = runOtaBatch(ota, registry);

        // 运维后台
        OpsConsole ops = new OpsConsole(registry, stateCache, alerts, consumer, ota);
        ops.print();

        // ---- 验收断言 ----
        AtomicInteger pass = new AtomicInteger();
        // ① 接入层：校验/去重/坏帧拦截计数精确
        check(pass, ingest.accepted() == 3L * FRAMES_PER_VEHICLE, "接入：3 车 × 400 帧全部接受入总线");
        check(pass, ingest.duplicates() == 9, "接入：3 车各 3 次重发全部判重");
        check(pass, ingest.rejected() == 6, "接入：6 条坏帧全部被拒");
        check(pass, bus.totalProduced() == 3L * FRAMES_PER_VEHICLE, "总线：恰好接收 1200 帧(去重/坏帧未污染)");
        // ② 消费层：drain 完积压、状态缓存与轨迹落库
        check(pass, drained == 1200 && consumer.lag() == 0, "消费：drain 1200 帧且积压归零");
        check(pass, stateCache.size() == 3 && stateCache.all().stream().allMatch(s -> s.seq() == FRAMES_PER_VEHICLE),
                "状态缓存：3 台车最新帧收敛到 seq=" + FRAMES_PER_VEHICLE);
        check(pass, trackStore.totalPoints() == 1200, "轨迹：1200 个点全部落库");
        // ③ 设备域：上报车辆在线，未上报仍 REGISTERED
        check(pass, registry.countByStatus(DeviceRegistry.Status.ONLINE) == 3, "设备：3 台上报车在线");
        // ④ 告警引擎：低电与过热各一条活跃告警
        check(pass, alerts.activeCount() == 2, "告警：LOW_SOC + MOTOR_OVERTEMP 各 1 条活跃");
        // ⑤ OTA：批次结果 + 失败车回滚 + 固件升级
        check(pass, batch.count(OtaPlatform.TaskState.SUCCEEDED) == 2, "OTA：2 台升级成功");
        check(pass, batch.count(OtaPlatform.TaskState.ROLLED_BACK) == 1, "OTA：失败车已回滚(ROLLED_BACK)");
        check(pass, registry.findByVin("LSV0000004").orElseThrow().fwVersion().equals("FW 2.2.0"),
                "OTA：4 号车固件已升到 FW 2.2.0");
        check(pass, batch.audit().size() >= 8 && ota.audit().size() >= 2, "审计：批次与平台操作均可回溯");
        // ⑥ 运维台聚合读数
        OpsConsole.OpsView view = ops.snapshot();
        check(pass, view.totalVehicles() == 6 && view.onlineVehicles() == 3
                        && view.activeAlerts() == 2 && view.busLag() == 0,
                "运维台：6 车 / 在线 3 / 告警 2 / 无积压，聚合读数一致");
        System.out.printf("ALL PASS: %d/14%n", pass.get());
    }

    /** 一台模拟车：发送 400 帧，中途重发 3 次、注入 2 条坏帧；末帧按需构造告警条件。 */
    private static void reportCar(String vin, IngestService ingest, boolean lowSocEnd, boolean overheatEnd) {
        for (long seq = 1; seq <= FRAMES_PER_VEHICLE; seq++) {
            double soc = 60 + (seq % 30);
            double kmh = seq % 60;
            double temp = 35 + (seq % 25);
            if (seq == FRAMES_PER_VEHICLE && lowSocEnd) {
                soc = 8;                       // 末帧低电：触发 LOW_SOC
            }
            if (seq == FRAMES_PER_VEHICLE && overheatEnd) {
                temp = 135;                    // 末帧过热：触发 MOTOR_OVERTEMP
            }
            ingest.submit(frame(vin, seq, soc, kmh, temp));
            if (seq == 100 || seq == 200 || seq == 300) {
                ingest.submit(frame(vin, seq, soc, kmh, temp));   // 故意重发：应判 dup
            }
            if (seq == 150 || seq == 350) {
                ingest.submit("T|" + vin + "|bad|not|frame");      // 坏帧：应被拒
            }
        }
    }

    private static String frame(String vin, long seq, double soc, double kmh, double temp) {
        return String.format("T|%s|%d|%.1f|%.1f|%.1f", vin, seq, soc, kmh, temp);
    }

    private static OtaPlatform.OtaBatch runOtaBatch(OtaPlatform ota, DeviceRegistry registry) {
        ota.publish("1.4.0");
        ota.publish("2.0.0");
        ota.publish("2.2.0");
        List<String> targets = List.of("LSV0000004", "LSV0000005", "LSV0000006");
        OtaPlatform.OtaBatch batch = ota.createBatch("OTA-2025-001", "2.2.0", targets);
        for (String vin : targets) {
            batch.advance(vin, OtaPlatform.TaskState.PENDING, OtaPlatform.TaskState.DOWNLOADING);
            batch.advance(vin, OtaPlatform.TaskState.DOWNLOADING, OtaPlatform.TaskState.INSTALLING);
        }
        // 4 号车成功、5 号车失败、6 号车成功
        batch.advance("LSV0000004", OtaPlatform.TaskState.INSTALLING, OtaPlatform.TaskState.SUCCEEDED);
        batch.advance("LSV0000005", OtaPlatform.TaskState.INSTALLING, OtaPlatform.TaskState.FAILED);
        batch.advance("LSV0000006", OtaPlatform.TaskState.INSTALLING, OtaPlatform.TaskState.SUCCEEDED);
        // 失败车回滚，成功车固件生效(写设备档案)
        batch.rollback("LSV0000005");
        registry.upgradeFirmware("LSV0000004", "FW 2.2.0");
        registry.upgradeFirmware("LSV0000006", "FW 2.2.0");
        return batch;
    }

    private static String MODEL(int i) {
        return i <= 4 ? "EV-Sedan" : "EV-Truck";
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
