// examples/ex04-alert-rule-engine/AlertEngineDemo.java —— 规则引擎主入口
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：
//   javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//   java -cp /tmp/tl21-cls:spi-resources AlertEngineDemo
// 期望：SPI 发现 2 个规则，三个数据源中 CPU 高水位与磁盘过热各自命中，健康数据源零告警。
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class AlertEngineDemo {
    public static void main(String[] args) {
        AlertEngine engine = new AlertEngine();

        AlertRule.MetricSnapshot cpuHighSource =
                new AlertRule.MetricSnapshot("SRC-000001", 1, 92.0, 40.0, 50.0);   // CPU 92%（>85 高水位）
        AlertRule.MetricSnapshot diskHotSource =
                new AlertRule.MetricSnapshot("SRC-000002", 2, 66.0, 90.0, 82.0);   // 磁盘 82℃（>75 过热）
        AlertRule.MetricSnapshot healthySource =
                new AlertRule.MetricSnapshot("SRC-000003", 3, 66.0, 60.0, 50.0);

        List<String> hitsA = engine.evaluateAll(cpuHighSource);
        List<String> hitsB = engine.evaluateAll(diskHotSource);
        List<String> hitsC = engine.evaluateAll(healthySource);

        AtomicInteger pass = new AtomicInteger();
        check(pass, engine.rules().size() == 2, "SPI 发现 2 个规则实现(而非硬编码)");
        check(pass, hitsA.size() == 1 && hitsA.get(0).startsWith("CPU_HIGH_WATERMARK"),
                "高水位数据源命中 CPU_HIGH_WATERMARK");
        check(pass, hitsB.size() == 1 && hitsB.get(0).startsWith("DISK_OVERHEAT"),
                "过热数据源命中 DISK_OVERHEAT");
        check(pass, hitsC.isEmpty(), "健康数据源零告警");

        System.out.println("-- 求值输出(代理日志在行首) --");
        System.out.println("高水位数据源: " + hitsA);
        System.out.println("过热数据源: " + hitsB);
        System.out.println("健康数据源: " + hitsC);
        System.out.printf("ALL PASS: %d/4%n", pass.get());
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
