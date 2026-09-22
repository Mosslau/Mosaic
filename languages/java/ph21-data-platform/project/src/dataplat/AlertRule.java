// project/src/dataplat/AlertRule.java —— 告警规则接口(可插拔：新增告警 = 新增实现并注册)
package dataplat;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/dataplat/*.java
import java.util.Optional;

public interface AlertRule {
    String name();
    String description();
    /** 对一条已入库的数据源最新状态求值：命中返回告警文案。 */
    Optional<String> evaluate(SourceStateCache.SourceState state);
}
