// examples/ex04-alert-rule-engine/AlertEngine.java —— 告警引擎：SPI 装载 + 动态代理计时 + 求值
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：
//   javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//   java -cp /tmp/tl21-cls:spi-resources AlertEngineDemo
// classpath 必须带上 spi-resources，ServiceLoader 才能读到 META-INF/services/AlertRule。
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.ArrayList;
import java.util.List;
import java.util.ServiceLoader;

/**
 * 规则引擎由三件事拼成(兑现 ph20 的 SPI + 动态代理预告)：
 *   1. ServiceLoader.load(AlertRule.class) —— 运行时发现实现，引擎代码不写死规则类；
 *   2. JDK 动态代理包装每个规则 —— 在 evaluate 前后统一埋点(耗时/命中计数)，不改规则代码；
 *   3. 顺序求值，把命中聚合返回 —— 引擎只关心 AlertRule 接口。
 */
public final class AlertEngine {
    private final List<AlertRule> rules;

    public AlertEngine() {
        this.rules = new ArrayList<>();
        for (AlertRule raw : ServiceLoader.load(AlertRule.class)) {
            this.rules.add(timingProxy(raw));       // 每个 SPI 规则外面再包一层代理
        }
    }

    public List<AlertRule> rules() { return rules; }

    /** 动态代理：拦截 evaluate，先计时、调真实规则、再记录命中数。 */
    private static AlertRule timingProxy(AlertRule target) {
        return (AlertRule) Proxy.newProxyInstance(
                AlertRule.class.getClassLoader(),
                new Class<?>[] { AlertRule.class },
                new InvocationHandler() {
                    @Override
                    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
                        if (method.getName().equals("evaluate")) {
                            long start = System.nanoTime();
                            Object result = method.invoke(target, args);
                            long costMs = (System.nanoTime() - start) / 1_000_000;
                            String sourceId = args[0] == null ? "-" : ((AlertRule.MetricSnapshot) args[0]).sourceId();
                            System.out.printf("  [proxy] rule=%s sourceId=%s costMs=%d%n",
                                    target.name(), sourceId, costMs);
                            return result;
                        }
                        return method.invoke(target, args);
                    }
                });
    }

    /** 对一条指标帧跑全部规则，收集命中告警。 */
    public List<String> evaluateAll(AlertRule.MetricSnapshot frame) {
        List<String> hits = new ArrayList<>();
        for (AlertRule rule : rules) {
            rule.evaluate(frame).ifPresent(hit -> hits.add(rule.name() + ": " + hit.message()));
        }
        return hits;
    }
}
