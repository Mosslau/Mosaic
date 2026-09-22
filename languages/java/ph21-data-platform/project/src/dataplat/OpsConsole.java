// project/src/dataplat/OpsConsole.java —— 运维后台：跨域聚合视图
package dataplat;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/dataplat/*.java
//
// 运维后台是各域的「只读聚合器」，不拥有数据(数据在各域 store)。
// 聚合项：节点在线率 / 实时状态快照 / 活跃告警 / 总线积压 / 版本发布批次进度。
public final class OpsConsole {
    private final NodeRegistry registry;
    private final SourceStateCache stateCache;
    private final AlertEngine alertEngine;
    private final MetricConsumer consumer;
    private final ReleasePlatform ota;

    public OpsConsole(NodeRegistry registry, SourceStateCache stateCache, AlertEngine alertEngine,
                      MetricConsumer consumer, ReleasePlatform ota) {
        this.registry = registry;
        this.stateCache = stateCache;
        this.alertEngine = alertEngine;
        this.consumer = consumer;
        this.ota = ota;
    }

    /** 运营总览(所有字段为快照值，可被验收断言读取)。 */
    public OpsView snapshot() {
        long online = registry.countByStatus(NodeRegistry.Status.ONLINE);
        double onlineRate = registry.size() == 0 ? 0 : online * 100.0 / registry.size();
        return new OpsView(registry.size(), online, onlineRate,
                alertEngine.activeCount(), consumer.lag(), stateCache.size());
    }

    /** 打印运维首页文本：总览 + 每个数据源明细 + 版本发布批次进度。 */
    public void print() {
        OpsView v = snapshot();
        System.out.println("+----------------------- 运维总览 -----------------------+");
        System.out.printf("  数据源 %d | 在线 %d (%.0f%%) | 活跃告警 %d | 总线积压 %d | 状态缓存 %d%n",
                v.totalVehicles(), v.onlineVehicles(), v.onlineRatePct(),
                v.activeAlerts(), v.busLag(), v.stateCount());
        System.out.println("  数据源明细:");
        for (NodeRegistry.Source veh : registry.all()) {
            SourceStateCache.SourceState st = stateCache.latest(veh.sourceId());
            String state = st == null ? "no-frame" : "cpu=" + st.cpuPct() + "% seq=" + st.seq();
            System.out.printf("    %s %-9s fw=%-5s [%s]%n", veh.sourceId(), veh.status(),
                    veh.fwVersion(), state);
        }
        for (ReleasePlatform.ReleaseBatch b : ota.allBatches()) {
            System.out.printf("    版本发布batch %s -> %s | 成功=%d 失败=%d 回滚=%d 进行中=%d%n",
                    b.id(), b.target(), b.count(ReleasePlatform.TaskState.SUCCEEDED),
                    b.count(ReleasePlatform.TaskState.FAILED), b.count(ReleasePlatform.TaskState.ROLLED_BACK),
                    b.vehicleCount() - (int) (b.count(ReleasePlatform.TaskState.SUCCEEDED)
                            + b.count(ReleasePlatform.TaskState.FAILED)
                            + b.count(ReleasePlatform.TaskState.ROLLED_BACK)));
        }
        System.out.println("+--------------------------------------------------------+");
    }

    public record OpsView(int totalVehicles, long onlineVehicles, double onlineRatePct,
                          long activeAlerts, long busLag, int stateCount) { }
}
