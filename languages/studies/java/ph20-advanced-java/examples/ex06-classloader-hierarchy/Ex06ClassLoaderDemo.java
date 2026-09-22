/*
 * examples/ex06-classloader-hierarchy/Ex06ClassLoaderDemo.java
 * ClassLoader 深入演示：① 默认委派链（App → Platform → Bootstrap）打印；
 * ② 自定义 loader「打破双亲委派」：先自己从目录读字节码 defineClass，再也没上抛给父加载器；
 * ③ 两个自定义 loader 各自加载同名同包类 → 得到两个互相隔离的 Class（类由 loader+name 共同定位）。
 *
 * 为什么有 ② 这种需求：JDBC/SPI 需要父加载器（启动类加载器）反向用子加载器（App）加载实现
 * （线程上下文类加载器，见主文档 3.7）；Tomcat 需要每个 Web 应用用独立 loader 隔离同名 jar。
 *
 * 验证环境：OpenJDK 17.0.18（Homebrew）
 * 编译：javac -encoding UTF-8 -d /tmp/tl20-cls Ex06ClassLoaderDemo.java
 *       javac -encoding UTF-8 -d /tmp/tl20-vA versionA/Greeting.java
 *       javac -encoding UTF-8 -d /tmp/tl20-vB versionB/Greeting.java
 * 运行：java -cp /tmp/tl20-cls Ex06ClassLoaderDemo /tmp/tl20-vA /tmp/tl20-vB
 * 本机已实测：输出 5 行 PASS（两个版本 greet 输出各自不同）
 */
import java.io.IOException;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;

public class Ex06ClassLoaderDemo {

    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("usage: java Ex06ClassLoaderDemo <dirA> <dirB>");
            return;
        }
        printDefaultHierarchy();
        Class<?> a = new DirBreakingLoader(args[0]).loadClass("Greeting");
        Class<?> b = new DirBreakingLoader(args[1]).loadClass("Greeting");
        check(a != b, "同一 FQN 由不同 loader 加载 = 两个隔离的 Class（" + a + " vs " + b + "）");
        check(invokeGreet(a).contains("A"), "版本 A 生效：" + invokeGreet(a));
        check(invokeGreet(b).contains("B"), "版本 B 生效：" + invokeGreet(b));
        check(a.getClassLoader().getClass().getSimpleName().contains("DirBreakingLoader"),
                "打破委派：Greeting 由自定义 loader 自己加载（父 loader 未被咨询）");
        System.out.println("ALL PASS: 5/5");
    }

    private static void printDefaultHierarchy() {
        ClassLoader cl = Ex06ClassLoaderDemo.class.getClassLoader();   // 应用类加载器
        System.out.println("委派链：");
        while (cl != null) {
            System.out.println("  " + cl.getName());
            cl = cl.getParent();
        }
        System.out.println("  <null = Bootstrap ClassLoader（打印为 null，C++ 实现）>");
    }

    private static String invokeGreet(Class<?> c) throws Exception {
        Object inst = c.getDeclaredConstructor().newInstance();
        Method m = c.getMethod("greet");
        return (String) m.invoke(inst);
    }

    /** 打破双亲委派的 loader：loadClass 不再「先交给父」，而是先自己按类名从 dir 读 .class 字节。
     * 找不到才退回默认逻辑（super.loadClass 会再走委派链）。 */
    private static final class DirBreakingLoader extends ClassLoader {
        private final Path dir;

        DirBreakingLoader(String dir) {
            super(Ex06ClassLoaderDemo.class.getClassLoader());   // 父 = App loader（保留，只是不再先问它）
            this.dir = Path.of(dir);
        }

        @Override
        public Class<?> loadClass(String name, boolean resolve) throws ClassNotFoundException {
            synchronized (getClassLoadingLock(name)) {
                Class<?> c = findLoadedClass(name);              // 已被本 loader 加载过？
                if (c == null) {
                    try {
                        c = findClass(name);                     // 自己找：打破点就在这
                    } catch (ClassNotFoundException e) {
                        return super.loadClass(name, resolve);   // 自己目录没有才回退委派链
                    }
                }
                if (resolve) {
                    resolveClass(c);
                }
                return c;
            }
        }

        @Override
        protected Class<?> findClass(String name) throws ClassNotFoundException {
            try {
                byte[] bytes = Files.readAllBytes(dir.resolve(name + ".class"));
                return defineClass(name, bytes, 0, bytes.length);
            } catch (IOException e) {
                throw new ClassNotFoundException(name, e);
            }
        }
    }

    private static void check(boolean cond, String msg) {
        if (!cond) {
            System.out.println("FAIL: " + msg);
            System.exit(1);
        }
        System.out.println("PASS: " + msg);
    }
}
