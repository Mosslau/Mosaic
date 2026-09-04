// project/src/vehicleiot/AlertRule.java —— 告警规则接口(可插拔：新增告警 = 新增实现并注册)
package vehicleiot;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/vehicleiot/*.java
import java.util.Optional;

public interface AlertRule {
    String name();
    String description();
    /** 对一条已入库的车辆最新状态求值：命中返回告警文案。 */
    Optional<String> evaluate(VehicleStateCache.VehicleState state);
}
