// examples/ex04-alert-rule-engine/AlertEngineDemo.java —— 规则引擎主入口
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：
//   javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//   java -cp /tmp/tl21-cls:spi-resources AlertEngineDemo
// 期望：SPI 发现 2 个规则，三辆车中低电与过热各自命中，健康车零告警。
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class AlertEngineDemo {
    public static void main(String[] args) {
        AlertEngine engine = new AlertEngine();

        AlertRule.TelemetrySnapshot lowSocCar =
                new AlertRule.TelemetrySnapshot("LSV000001", 1, 8.0, 40.0, 50.0);   // SOC 8%
        AlertRule.TelemetrySnapshot hotMotorCar =
                new AlertRule.TelemetrySnapshot("LSV000002", 2, 66.0, 90.0, 135.0);  // 电机 135℃
        AlertRule.TelemetrySnapshot healthyCar =
                new AlertRule.TelemetrySnapshot("LSV000003", 3, 66.0, 60.0, 50.0);

        List<String> hitsA = engine.evaluateAll(lowSocCar);
        List<String> hitsB = engine.evaluateAll(hotMotorCar);
        List<String> hitsC = engine.evaluateAll(healthyCar);

        AtomicInteger pass = new AtomicInteger();
        check(pass, engine.rules().size() == 2, "SPI 发现 2 个规则实现(而非硬编码)");
        check(pass, hitsA.size() == 1 && hitsA.get(0).startsWith("LOW_SOC"), "低电车辆命中 LOW_SOC");
        check(pass, hitsB.size() == 1 && hitsB.get(0).startsWith("MOTOR_OVERTEMP"), "过热车辆命中 MOTOR_OVERTEMP");
        check(pass, hitsC.isEmpty(), "健康车辆零告警");

        System.out.println("-- 求值输出(代理日志在行首) --");
        System.out.println("低电车: " + hitsA);
        System.out.println("过热车: " + hitsB);
        System.out.println("健康车: " + hitsC);
        System.out.printf("ALL PASS: %d/4%n", pass.get());
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
