// examples/ex08-ops-console/OpsMetrics.java —— 运维后台聚合的数据快照
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
import java.util.List;

/**
 * 运维后台的数据来源不是一张表，而是跨域的**聚合视图**：节点域给在线数、告警域给活跃告警、
 * 版本发布域给进行中批次、指标域给消息吞吐。本 record 把各域快照归一成一张可渲染的运营报表。
 */
record OpsMetrics(
        int totalVehicles,      // 节点域：注册数据源总数
        int onlineVehicles,     // 节点域：当前在线
        int activeAlerts,       // 告警域：未关闭告警
        int otaRunningBatches,  // 版本发布域：进行中批次
        long lastMinMsgs,       // 指标域：最近一分钟消息数
        long totalMsgs) {       // 指标域：累计消息数

    static OpsMetrics zero() {
        return new OpsMetrics(0, 0, 0, 0, 0, 0);
    }
}
