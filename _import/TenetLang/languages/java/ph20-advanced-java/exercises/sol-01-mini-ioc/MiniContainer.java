/*
 * exercises/sol-01-mini-ioc/MiniContainer.java —— 练习 1 参考实现（容器核心，约 60 行）
 * 「手写简易 IOC」的最小内核：容器持有 接口/类 → 实现类 的注册表，
 * getBean 时用反射挑「参数最多的构造器」，按参数类型递归解析依赖并注入——
 * 对象创建、依赖查找、单例缓存三件事全由容器完成，业务代码不 new、不找依赖。
 *
 * 与 project/ 的注解驱动 IOC 分工：本项目展示「容器本质 = 注册表 + 反射装配 + 单例缓存」，
 * project 展示「注解扫描 + 容器生命周期」的工程形态。
 *
 * 验证环境：OpenJDK 17.0.18（Homebrew）
 * 编译：javac -encoding UTF-8 -d /tmp/tl20-cls MiniContainer.java MiniIocDemo.java
 * 运行：java -cp /tmp/tl20-cls MiniIocDemo
 * 本机已实测：4 段输出 PASS
 */
import java.lang.reflect.Constructor;
import java.util.HashMap;
import java.util.Map;

/** 最小 IOC 容器：接口 → 实现 注册；单例缓存；构造器依赖注入（只处理构造注入，够教学）。 */
public final class MiniContainer {

    private final Map<Class<?>, Class<?>> registrations = new HashMap<>();  // 接口/类 → 实现类
    private final Map<Class<?>, Object> singletons = new HashMap<>();        // 已创建的单例缓存

    /** 注册：把「接口/超类」映射到「具体实现类」。 */
    public <T> void register(Class<T> type, Class<? extends T> impl) {
        registrations.put(type, impl);
    }

    /** 取 bean：已创建返回缓存实例；未创建则反射装配后缓存（本容器的默认作用域 = 单例）。 */
    @SuppressWarnings("unchecked")
    public <T> T getBean(Class<T> type) {
        Object existing = singletons.get(type);
        if (existing != null) {
            return (T) existing;
        }
        Object created = createInstance(resolveImpl(type));
        singletons.put(type, created);
        return (T) created;
    }

    /** 找实现类：已注册就直接用，未注册且自身可实例化（非接口/抽象类）就用自身。 */
    private Class<?> resolveImpl(Class<?> type) {
        Class<?> impl = registrations.get(type);
        return impl != null ? impl : type;
    }

    /** 反射装配：挑「参数最多」的构造器，每个参数递归 getBean，newInstance 完成注入。
     *  这是 IOC 与「手动 new 依赖」的分水岭：容器自己解决依赖图。 */
    private Object createInstance(Class<?> impl) {
        try {
            Constructor<?> ctor = pickGreediestConstructor(impl);
            Class<?>[] paramTypes = ctor.getParameterTypes();
            Object[] args = new Object[paramTypes.length];
            for (int i = 0; i < paramTypes.length; i++) {
                args[i] = getBean(paramTypes[i]);          // 递归注入：参数本身也由容器管
            }
            return ctor.newInstance(args);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("无法装配 " + impl.getName(), e);
        }
    }

    /** 构造器注入要挑的往往是「参数最多的那个构造器」——依赖最多的装配点。 */
    private static Constructor<?> pickGreediestConstructor(Class<?> impl) {
        Constructor<?>[] ctors = impl.getDeclaredConstructors();
        Constructor<?> best = ctors[0];
        for (Constructor<?> c : ctors) {
            if (c.getParameterCount() > best.getParameterCount()) {
                best = c;
            }
        }
        best.setAccessible(true);                          // 私有构造器也要能注入（框架常见做法）
        return best;
    }
}
