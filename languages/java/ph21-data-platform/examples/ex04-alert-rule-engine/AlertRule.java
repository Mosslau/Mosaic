// examples/ex04-alert-rule-engine/AlertRule.java —— 告警规则 SPI 接口(兑现 ph20 SPI 预告)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
import java.util.List;
import java.util.Optional;

/**
 * 规则引擎把「每种告警怎么判定」声明成可插拔实现：调方只依赖本接口，
 * 具体规则在 META-INF/services/AlertRule 里登记(见 spi-resources)，由 ServiceLoader 发现。
 * 新增一种告警 = 新增一个实现类 + 加一行登记，引擎零改动。
 */
public interface AlertRule {
    /** 规则名(用于审计与去重，如 "BMS_OVERTEMP")。 */
    String name();
    /** 对单条遥测帧求值：命中返回告警，未命中返回 empty。 */
    Optional<AlertHit> evaluate(TelemetrySnapshot frame);
    /** 告警阈值说明，供运维后台展示。 */
    String description();

    /** 一条告警命中(规则 + 帧上下文)，由引擎补时间戳后发给下游。 */
    record AlertHit(String vin, String message) { }

    /** 引擎喂给规则的最小帧视图(规则只读，不改帧)。 */
    record TelemetrySnapshot(String vin, long seq, double socPct, double kmh, double motorTempC) { }

    /** 汇总工具：SPI 加载到的全部规则都返回各自 name。 */
    static List<String> names(List<AlertRule> rules) {
        return rules.stream().map(AlertRule::name).toList();
    }
}
