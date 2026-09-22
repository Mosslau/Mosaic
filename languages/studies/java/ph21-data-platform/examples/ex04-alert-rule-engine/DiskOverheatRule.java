// examples/ex04-alert-rule-engine/DiskOverheatRule.java —— SPI 实现 2：磁盘过热告警
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
import java.util.Optional;

public final class DiskOverheatRule implements AlertRule {
    private static final double DISK_TEMP_LIMIT = 75.0;  // 磁盘温度上限(示例值，与全阶段口径一致)

    @Override public String name() { return "DISK_OVERHEAT"; }
    @Override public String description() { return "磁盘温度 > 75℃ 触发过热告警"; }

    @Override
    public Optional<AlertHit> evaluate(MetricSnapshot f) {
        if (f.diskTempC() > DISK_TEMP_LIMIT) {
            return Optional.of(new AlertHit(f.sourceId(), "磁盘过热: " + f.diskTempC() + "℃"));
        }
        return Optional.empty();
    }
}
