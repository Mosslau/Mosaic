// examples/ex04-alert-rule-engine/LowSocRule.java —— SPI 实现 1：SOC 过低告警
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
import java.util.Optional;

public final class LowSocRule implements AlertRule {
    private static final double SOC_THRESHOLD = 15.0;   // 低于 15% 提醒充电/脱困

    @Override public String name() { return "LOW_SOC"; }
    @Override public String description() { return "SOC < 15% 触发低电量告警"; }

    @Override
    public Optional<AlertHit> evaluate(TelemetrySnapshot f) {
        if (f.socPct() < SOC_THRESHOLD) {
            return Optional.of(new AlertHit(f.vin(), "低电量: soc=" + f.socPct() + "%"));
        }
        return Optional.empty();
    }
}
