// examples/ex08-ops-console/OpsDashboard.java —— 运维后台：多源指标聚合 + 文本渲染
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//
// 教学点：运维后台不该直接查业务库，而是**订阅各域的指标流**做本地聚合(ph17 的 MQ 派上用场：
// 设备域发 online/offline 事件、告警域发 alert 事件、遥测域发计数)。本类演示「聚合 + 渲染」，
// 真实后台把渲染换成前端图表、把指标流换成 Prometheus/自建时序聚合(ph19 监控)。
import java.util.ArrayList;
import java.util.List;

public final class OpsDashboard {
    private final List<MetricEvent> events = new ArrayList<>();   // 各域事件流(演示版：直接喂)

    /** 领域事件(生产环境来自 Kafka 各 topic，见主文档 3.3)。 */
    public enum MetricEvent {
        VEHICLE_ONLINE, VEHICLE_OFFLINE, VEHICLE_REGISTERED, ALERT_OPENED,
        ALERT_CLOSED, OTA_BATCH_STARTED, OTA_BATCH_FINISHED, TELEMETRY_RECEIVED
    }

    /** 喂一条域事件(真实形态是各消费组回调这里)。 */
    public synchronized void onEvent(MetricEvent e) {
        events.add(e);
    }

    /** 汇总为运营快照：事件流 → 各域当前状态。 */
    public synchronized OpsMetrics snapshot() {
        int total = 0, online = 0, activeAlerts = 0, otaRunning = 0;
        long totalMsgs = 0;
        for (MetricEvent e : events) {
            switch (e) {
                case VEHICLE_REGISTERED -> total++;
                case VEHICLE_ONLINE -> online++;
                case VEHICLE_OFFLINE -> online--;
                case ALERT_OPENED -> activeAlerts++;
                case ALERT_CLOSED -> activeAlerts--;
                case OTA_BATCH_STARTED -> otaRunning++;
                case OTA_BATCH_FINISHED -> otaRunning--;
                case TELEMETRY_RECEIVED -> totalMsgs++;
            }
        }
        return new OpsMetrics(total, online, activeAlerts, otaRunning, 0, totalMsgs);
    }

    /** 渲染成运维后台首页文本(教学版；生产换 HTML/前端框架)。 */
    public static String render(OpsMetrics m) {
        return String.format("""
                +------------------------ 运维总览 ------------------------+
                 注册车辆   %d     在线车辆   %d     在线率   %.0f%%
                 活跃告警   %d     进行中 OTA %d     累计消息  %d
                +----------------------------------------------------------+
                """, m.totalVehicles(), m.onlineVehicles(),
                m.totalVehicles() == 0 ? 0 : m.onlineVehicles() * 100.0 / m.totalVehicles(),
                m.activeAlerts(), m.otaRunningBatches(), m.totalMsgs());
    }
}
