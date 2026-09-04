// project/src/vehicleiot/AlertEngine.java —— 告警引擎：规则表 + 求值 + 活跃告警表
package vehicleiot;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/vehicleiot/*.java
//
// 引擎本身不含任何业务阈值：规则以 List<AlertRule> 注入(依赖倒置)。
// 生产上规则可由 SPI 装载(见 examples/ex04)，这里用内置两条规则做最小演示；
// 活跃告警表按 (vin, rule) 键去重，同一车辆同一告警只记一条。
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public final class AlertEngine {
    public record ActiveAlert(String vin, String ruleName, String message) { }

    private final List<AlertRule> rules;
    private final ConcurrentHashMap<String, ActiveAlert> active = new ConcurrentHashMap<>();

    public AlertEngine(List<AlertRule> rules) {
        this.rules = List.copyOf(rules);
    }

    /** 对车辆最新状态跑全部规则；新命中的告警进入活跃表(幂等去重)。 */
    public void evaluate(VehicleStateCache.VehicleState state) {
        for (AlertRule rule : rules) {
            rule.evaluate(state).ifPresent(msg -> {
                active.putIfAbsent(key(state.vin(), rule.name()),
                        new ActiveAlert(state.vin(), rule.name(), msg));
            });
        }
    }

    public void clear(String vin, String ruleName) {
        active.remove(key(vin, ruleName));
    }

    public List<ActiveAlert> activeAlerts() {
        return active.values().stream()
                .sorted((a, b) -> a.vin().compareTo(b.vin())).toList();
    }

    public int activeCount() { return active.size(); }

    private static String key(String vin, String ruleName) { return vin + "#" + ruleName; }
}
