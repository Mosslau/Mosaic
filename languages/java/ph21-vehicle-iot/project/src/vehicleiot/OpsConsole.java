// project/src/vehicleiot/OpsConsole.java —— 运维后台：跨域聚合视图
package vehicleiot;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/vehicleiot/*.java
//
// 运维后台是各域的「只读聚合器」，不拥有数据(数据在各域 store)。
// 聚合项：设备在线率 / 实时状态快照 / 活跃告警 / 总线积压 / OTA 批次进度。
public final class OpsConsole {
    private final DeviceRegistry registry;
    private final VehicleStateCache stateCache;
    private final AlertEngine alertEngine;
    private final TelemetryConsumer consumer;
    private final OtaPlatform ota;

    public OpsConsole(DeviceRegistry registry, VehicleStateCache stateCache, AlertEngine alertEngine,
                      TelemetryConsumer consumer, OtaPlatform ota) {
        this.registry = registry;
        this.stateCache = stateCache;
        this.alertEngine = alertEngine;
        this.consumer = consumer;
        this.ota = ota;
    }

    /** 运营总览(所有字段为快照值，可被验收断言读取)。 */
    public OpsView snapshot() {
        long online = registry.countByStatus(DeviceRegistry.Status.ONLINE);
        double onlineRate = registry.size() == 0 ? 0 : online * 100.0 / registry.size();
        return new OpsView(registry.size(), online, onlineRate,
                alertEngine.activeCount(), consumer.lag(), stateCache.size());
    }

    /** 打印运维首页文本：总览 + 每车明细 + OTA 批次进度。 */
    public void print() {
        OpsView v = snapshot();
        System.out.println("+----------------------- 运维总览 -----------------------+");
        System.out.printf("  车辆 %d | 在线 %d (%.0f%%) | 活跃告警 %d | 总线积压 %d | 状态缓存 %d%n",
                v.totalVehicles(), v.onlineVehicles(), v.onlineRatePct(),
                v.activeAlerts(), v.busLag(), v.stateCount());
        System.out.println("  车辆明细:");
        for (DeviceRegistry.Vehicle veh : registry.all()) {
            VehicleStateCache.VehicleState st = stateCache.latest(veh.vin());
            String state = st == null ? "no-frame" : "soc=" + st.socPct() + "% seq=" + st.seq();
            System.out.printf("    %s %-9s fw=%-5s [%s]%n", veh.vin(), veh.status(),
                    veh.fwVersion(), state);
        }
        for (OtaPlatform.OtaBatch b : ota.allBatches()) {
            System.out.printf("    OTA batch %s -> %s | 成功=%d 失败=%d 回滚=%d 进行中=%d%n",
                    b.id(), b.target(), b.count(OtaPlatform.TaskState.SUCCEEDED),
                    b.count(OtaPlatform.TaskState.FAILED), b.count(OtaPlatform.TaskState.ROLLED_BACK),
                    b.vehicleCount() - (int) (b.count(OtaPlatform.TaskState.SUCCEEDED)
                            + b.count(OtaPlatform.TaskState.FAILED)
                            + b.count(OtaPlatform.TaskState.ROLLED_BACK)));
        }
        System.out.println("+--------------------------------------------------------+");
    }

    public record OpsView(int totalVehicles, long onlineVehicles, double onlineRatePct,
                          long activeAlerts, long busLag, int stateCount) { }
}
