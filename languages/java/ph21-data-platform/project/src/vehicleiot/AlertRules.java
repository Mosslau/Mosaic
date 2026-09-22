// project/src/vehicleiot/AlertRules.java —— 内置告警规则实现(与引擎解耦的阈值)
package vehicleiot;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/vehicleiot/*.java
import java.util.Optional;

/** 引擎的规则库以「常量 + 纯函数」实现，便于单测与替换。 */
final class AlertRules {
    private AlertRules() { }

    /** SOC 低于 15% 视为低电量告警。 */
    static final class LowSocRule implements AlertRule {
        private static final double SOC_FLOOR = 15.0;
        @Override public String name()        { return "LOW_SOC"; }
        @Override public String description() { return "SOC < 15% 触发低电量告警"; }
        @Override public Optional<String> evaluate(VehicleStateCache.VehicleState s) {
            return s.socPct() < SOC_FLOOR ? Optional.of("soc=" + s.socPct() + "%") : Optional.empty();
        }
    }

    /** 电机温度超过 120℃ 视为过热告警。 */
    static final class OverheatRule implements AlertRule {
        private static final double MOTOR_TEMP_CEILING = 120.0;
        @Override public String name()        { return "MOTOR_OVERTEMP"; }
        @Override public String description() { return "电机温度 > 120℃ 触发过热告警"; }
        @Override public Optional<String> evaluate(VehicleStateCache.VehicleState s) {
            return s.motorTempC() > MOTOR_TEMP_CEILING ? Optional.of("motorTemp=" + s.motorTempC() + "℃")
                    : Optional.empty();
        }
    }
}
