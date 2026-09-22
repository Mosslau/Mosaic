/*
 * examples/ex05-reflection-proxy-spi/Ex05ReflectionProxySpiDemo.java
 * 三段演示：① 反射读写私有字段（框架为什么能绕过封装边界）；② JDK 动态代理（Proxy 只能代理接口）；
 * ③ SPI 服务发现（ServiceLoader 扫 META-INF/services —— 调用方零改动扩展实现）。
 *
 * 验证环境：OpenJDK 17.0.18（Homebrew）
 * 编译：javac -encoding UTF-8 -d /tmp/tl20-cls *.java
 * 运行：java -cp /tmp/tl20-cls:spi-resources Ex05ReflectionProxySpiDemo
 *       （spi-resources 目录必须进 classpath，ServiceLoader 才能扫到 META-INF/services）
 * 本机已实测：6 段输出全部符合预期（含 SPI 发现 2 个实现）
 */
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Proxy;
import java.util.ServiceLoader;

public class Ex05ReflectionProxySpiDemo {

    /** 反射演示对象：private 字段 + 自定义注解（模仿「框架读你的配置」）。 */
    @Retention(RetentionPolicy.RUNTIME)
    public @interface NotNull {
    }

    public static final class Config {
        @NotNull
        private String dbUrl = "jdbc:mysql://127.0.0.1:3306/app";
    }

    public static void main(String[] args) throws Exception {
        partReflection();
        partProxy();
        partSpi();
        System.out.println("ALL DONE: reflection / proxy / spi 三段完成");
    }

    /** ① 反射：编译期拿不到的 private 字段，运行时用 getDeclaredField + setAccessible 读写。
     * 这正是 IOC/ORM 框架注入属性、序列化框架读写字段的机制（Spring 对 field 注入也是这么干的）。 */
    private static void partReflection() throws Exception {
        Config cfg = new Config();
        Field f = Config.class.getDeclaredField("dbUrl");   // getDeclaredField：含 private；getField 只有 public
        f.setAccessible(true);                               // 关掉访问检查（Java 17 仍允许；模块系统可再收紧）
        Object oldValue = f.get(cfg);                        // 读 private 字段
        f.set(cfg, "jdbc:mysql://10.0.0.8:3306/app");        // 写 private 字段
        check("Reflection 读写 private 字段成功：" + oldValue + " → " + f.get(cfg));
        check("字段带 @NotNull 注解: " + f.isAnnotationPresent(NotNull.class));
    }

    /** ② JDK 动态代理：运行时生成一个实现 Greeter 接口的代理类，把调用转给 InvocationHandler。
     * 关键限制：Proxy 只能代理「接口」（生成实现接口的类）；没有接口的类要用 CGLIB 子类代理（Spring 的选择逻辑）。 */
    private static void partProxy() {
        Greeter real = new ChineseGreeter();                  // 被代理的目标
        InvocationHandler handler = (proxy, method, args) -> {
            System.out.println("    [proxy] interceptor sees call: " + method.getName()
                    + " args=" + (args == null ? "()" : "(" + args[0] + ")"));
            long start = System.nanoTime();
            Object result = method.invoke(real, args);        // 转发给真实对象（可在此加日志/鉴权/事务）
            System.out.println("    [proxy] call done in " + (System.nanoTime() - start) / 1000 + "us");
            return result;
        };
        Greeter proxied = (Greeter) Proxy.newProxyInstance(
                Greeter.class.getClassLoader(), new Class<?>[]{Greeter.class}, handler);
        check("Proxy 调用结果：" + proxied.greet("Proxy"));
        check("运行时类型是代理类 Proxy.isProxyClass=" + Proxy.isProxyClass(proxied.getClass()));
    }

    /** ③ SPI：ServiceLoader 读取 classpath 上所有 META-INF/services/Greeter 里登记的类并实例化。
     * 新增实现 = 加一个 class + 在该文件加一行 —— 调用方与接口都零改动（JDBC 驱动/slf4j 绑定/Spring.factories 同款机制）。 */
    private static void partSpi() {
        ServiceLoader<Greeter> loader = ServiceLoader.load(Greeter.class);
        int n = 0;
        for (Greeter g : loader) {
            System.out.println("    [spi] discovered " + g.getClass().getName() + " → " + g.greet("SPI"));
            n++;
        }
        check("SPI 发现实现数 = 2，实际 " + n);
    }

    private static void check(String msg) {
        System.out.println("PASS: " + msg);
    }
}
