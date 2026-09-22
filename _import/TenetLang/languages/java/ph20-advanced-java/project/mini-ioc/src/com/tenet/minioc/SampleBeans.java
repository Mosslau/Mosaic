/*
 * project/mini-ioc/src/com/tenet/minioc/SampleBeans.java
 * 演示组件集：构造器注入（EmailNotifier/OrderService）+ 字段注入（Metrics）+ 无依赖组件（Logger）。
 * 全部为包内可见类型即可——容器用反射 + setAccessible 装配，不需要 public（教学点）。
 */
package com.tenet.minioc;

/** 演示用的「服务接口」：实现注册进容器后，按接口类型解析依赖。 */
interface Notifier {
    String send(String msg);
}

/** 无依赖叶子组件：构造器缺省（无参），供其他 bean 注入。 */
@Component
final class Logger {
    private final java.util.List<String> history = new java.util.ArrayList<>();

    void log(String line) {
        history.add(line);
    }

    int size() {
        return history.size();
    }
}

/** 构造器注入 + 依赖接口：容器把「唯一实现」EmailNotifier 解析给构造参数 Notifier。 */
@Component
final class EmailNotifier implements Notifier {
    private final Logger logger;

    @Inject
    EmailNotifier(Logger logger) {                 // 构造器注入点（带 @Inject 的构造器优先被选中）
        this.logger = logger;
    }

    @Override
    public String send(String msg) {
        logger.log("email:" + msg);
        return "email#" + msg;
    }
}

/** 更上层的业务组件：只依赖接口 Notifier，不感知具体实现——IOC 让「面向接口编程」自动成立。 */
@Component
final class OrderService {
    private final Notifier notifier;

    @Inject
    OrderService(Notifier notifier) {              // 依赖 Notifier 接口 → 容器注入唯一实现 EmailNotifier
        this.notifier = notifier;
    }

    String place(String orderId) {
        return notifier.send("order-placed:" + orderId);
    }
}

/** 字段注入示例：创建后容器把 Logger 反射塞进 @Inject 字段。 */
@Component
final class Metrics {
    @Inject
    private Logger logger;                          // 字段注入点

    void record(String event) {
        logger.log("metric:" + event);
    }

    int totalLogged() {
        return logger.size();
    }
}
