// examples/ex04-alert-rule-engine/CpuWatermarkRule.java —— SPI 实现 1：CPU 过高告警
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
import java.util.Optional;

public final class CpuWatermarkRule implements AlertRule {
    private static final double CPU_WATERMARK_PCT = 85.0;   // 高于 85% 提示扩容/迁移任务

    @Override public String name() { return "CPU_HIGH_WATERMARK"; }
    @Override public String description() { return "CPU 使用率 > 85% 触发高水位告警"; }

    @Override
    public Optional<AlertHit> evaluate(MetricSnapshot f) {
        if (f.cpuPct() > CPU_WATERMARK_PCT) {
            return Optional.of(new AlertHit(f.sourceId(), "CPU 高水位: cpu=" + f.cpuPct() + "%"));
        }
        return Optional.empty();
    }
}
