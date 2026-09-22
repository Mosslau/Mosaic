// project/src/dataplat/AlertRules.java —— 内置告警规则实现(与引擎解耦的阈值)
package dataplat;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/dataplat/*.java
import java.util.Optional;

/** 引擎的规则库以「常量 + 纯函数」实现，便于单测与替换。 */
final class AlertRules {
    private AlertRules() { }

    /** CPU 高于 85% 视为资源高水位告警（与 examples/ex04 同口径）。 */
    static final class CpuWatermarkRule implements AlertRule {
        private static final double CPU_WATERMARK_PCT = 85.0;
        @Override public String name()        { return "CPU_HIGH_WATERMARK"; }
        @Override public String description() { return "CPU > 85% 触发高水位告警"; }
        @Override public Optional<String> evaluate(SourceStateCache.SourceState s) {
            return s.cpuPct() > CPU_WATERMARK_PCT
                    ? Optional.of("cpu=" + s.cpuPct() + "%") : Optional.empty();
        }
    }

    /** 磁盘温度超过 75℃ 视为过热告警（与 examples/ex04 同口径）。 */
    static final class DiskOverheatRule implements AlertRule {
        private static final double DISK_TEMP_LIMIT = 75.0;
        @Override public String name()        { return "DISK_OVERHEAT"; }
        @Override public String description() { return "磁盘温度 > 75℃ 触发过热告警"; }
        @Override public Optional<String> evaluate(SourceStateCache.SourceState s) {
            return s.diskTempC() > DISK_TEMP_LIMIT
                    ? Optional.of("diskTemp=" + s.diskTempC() + "℃") : Optional.empty();
        }
    }
}
