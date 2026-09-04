// examples/ex04-alert-rule-engine/OverheatRule.java —— SPI 实现 2：电机过热告警
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
import java.util.Optional;

public final class OverheatRule implements AlertRule {
    private static final double MOTOR_TEMP_LIMIT = 120.0;  // 电机温度上限(示例值)

    @Override public String name() { return "MOTOR_OVERTEMP"; }
    @Override public String description() { return "电机温度 > 120℃ 触发过热告警"; }

    @Override
    public Optional<AlertHit> evaluate(TelemetrySnapshot f) {
        if (f.motorTempC() > MOTOR_TEMP_LIMIT) {
            return Optional.of(new AlertHit(f.vin(), "电机过热: " + f.motorTempC() + "℃"));
        }
        return Optional.empty();
    }
}
