// examples/ex08-ops-console/OpsConsoleDemo.java —— 运维后台演示主入口
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：
//   javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//   java -cp /tmp/tl21-cls OpsConsoleDemo
// 期望：注册 3 车全部在线，1 条活跃告警，1 个 OTA 批次进行中，文本总览正确渲染。
import java.util.concurrent.atomic.AtomicInteger;

public final class OpsConsoleDemo {
    public static void main(String[] args) {
        OpsDashboard dashboard = new OpsDashboard();
        OpsDashboard.MetricEvent[] feed = {
                OpsDashboard.MetricEvent.VEHICLE_REGISTERED,     // 车 1
                OpsDashboard.MetricEvent.VEHICLE_REGISTERED,     // 车 2
                OpsDashboard.MetricEvent.VEHICLE_REGISTERED,     // 车 3
                OpsDashboard.MetricEvent.VEHICLE_ONLINE, OpsDashboard.MetricEvent.VEHICLE_ONLINE,
                OpsDashboard.MetricEvent.VEHICLE_ONLINE,
                OpsDashboard.MetricEvent.ALERT_OPENED,           // 低电告警
                OpsDashboard.MetricEvent.OTA_BATCH_STARTED,      // 一个升级批次
                OpsDashboard.MetricEvent.TELEMETRY_RECEIVED,     // 遥测消息计数(累计口径)
                OpsDashboard.MetricEvent.TELEMETRY_RECEIVED,
                OpsDashboard.MetricEvent.TELEMETRY_RECEIVED,
        };
        for (OpsDashboard.MetricEvent e : feed) {
            dashboard.onEvent(e);
        }

        OpsMetrics snapshot = dashboard.snapshot();
        System.out.print(OpsDashboard.render(snapshot));

        AtomicInteger pass = new AtomicInteger();
        check(pass, snapshot.totalVehicles() == 3, "注册车辆 = 3");
        check(pass, snapshot.onlineVehicles() == 3, "在线车辆 = 3");
        check(pass, snapshot.activeAlerts() == 1, "活跃告警 = 1");
        check(pass, snapshot.otaRunningBatches() == 1, "进行中 OTA = 1");
        check(pass, snapshot.totalMsgs() == 3, "累计消息 = 3(事件流语义，非滚动窗口)");
        System.out.printf("ALL PASS: %d/5%n", pass.get());
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
