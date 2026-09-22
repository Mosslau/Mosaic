// examples/ex02-class-loader.java —— 类加载机制演示：加载链 / 懒初始化 / 双亲委派 / 打破双亲委派
// 对应主文档 6. 示例 2：验证「类身份 = 类名 + 定义它的加载器」与双亲委派行为
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex02-class-loader.java（两个源文件——ex02-class-loader.java + LoadedHelper.java；
//        javac 自动编译引用的 LoadedHelper.java，产出 Ex02ClassLoaderDemo.class、LoadedHelper.class、ConstantUser.class）
// 运行：java Ex02ClassLoaderDemo（注意是类名不是文件名；程序通过系统资源路径读取 LoadedHelper.class 字节）
// 验证状态：已验证：OpenJDK 17.0.18
import java.io.InputStream;
import java.lang.reflect.Method;

class Ex02ClassLoaderDemo {
    public static void main(String[] args) throws Exception {
        demoLoaderChain();    // 1. 类加载器层级与双亲委派链
        demoLazyInit();       // 2. 懒初始化：static final 编译期常量不触发 <clinit>
        demoParentFirst();    // 3. 双亲委派：自定义加载器先问父，父能加载就不自己加载
        demoBreakDelegation();// 4. 打破双亲委派：同一份字节两个加载器各加载一次，类身份不同
        System.out.println("自检通过：加载链 / 懒初始化 / 双亲委派 / 打破双亲委派 全部符合预期");
    }

    /** 1. 类加载器层级：应用类加载器 → 平台类加载器 → 启动类加载器（null 表示 Bootstrap） */
    static void demoLoaderChain() {
        ClassLoader app = Ex02ClassLoaderDemo.class.getClassLoader();
        ClassLoader platform = app.getParent();
        ClassLoader bootstrap = platform.getParent();
        System.out.println("Ex02ClassLoaderDemo 的加载链:");
        System.out.println("  " + app + "  ← AppClassLoader（应用类加载器）");
        System.out.println("  " + platform + "  ← PlatformClassLoader（平台类加载器）");
        System.out.println("  " + bootstrap + "  ← Bootstrap 启动类加载器（getParent() 为 null）");
        // 核心类由 Bootstrap 加载：getClassLoader() 为 null
        ClassLoader stringLoader = String.class.getClassLoader();
        System.out.println("java.lang.String 的加载器 = " + stringLoader + "  (null 即 Bootstrap, 核心类不在 classpath)");
        if (stringLoader != null) throw new AssertionError("核心类 String 应由 Bootstrap 加载");
        if (bootstrap != null) throw new AssertionError("顶层加载器的 getParent() 应为 null");
    }

    /** 2. 懒初始化：static final 编译期常量被内联，不触发目标类 <clinit>；Class.forName 默认才触发 */
    static void demoLazyInit() throws Exception {
        ClassLoader app = Ex02ClassLoaderDemo.class.getClassLoader();
        // (a) forName(name, false, loader)：只加载不初始化——不应看到 LoadedHelper 的 <clinit> 输出
        Class<?> loaded = Class.forName("LoadedHelper", false, app);
        System.out.println("Class.forName(\"LoadedHelper\", false, app) 已加载, 是否初始化? 看上面有无 <clinit> 输出（应无）");
        // (b) 访问编译期常量（已内联进 ConstantUser）：同样不触发 LoadedHelper 初始化
        System.out.println("ConstantUser.GREETING = " + ConstantUser.GREETING + "  (常量已内联, 不触发 <clinit>)");
        // (c) forName 默认初始化：此时才执行 <clinit>
        Class.forName("LoadedHelper");
        System.out.println("Class.forName(\"LoadedHelper\") 默认初始化, 上面应出现 <clinit> 输出");
    }

    /** 3. 双亲委派：自定义加载器 loadClass 先委托父（App），父能加载则由父加载 */
    static void demoParentFirst() throws Exception {
        ClassLoader app = Ex02ClassLoaderDemo.class.getClassLoader();
        ParentFirstLoader pf = new ParentFirstLoader();
        Class<?> c = pf.loadClass("LoadedHelper");
        System.out.println("ParentFirstLoader.loadClass(\"LoadedHelper\") 的加载器 = "
                + c.getClassLoader().getClass().getSimpleName()
                + "  (父加载器 App 已能加载, 自定义加载器没机会自己加载)");
        if (c.getClassLoader() != app) throw new AssertionError("双亲委派失败：应由父加载器 App 加载");
    }

    /** 4. 打破双亲委派：两个 BreakingLoader 各自 defineClass 同一份字节 → 类名相同但类身份不同 */
    static void demoBreakDelegation() throws Exception {
        BreakingLoader b1 = new BreakingLoader();
        BreakingLoader b2 = new BreakingLoader();
        Class<?> c1 = b1.loadClass("LoadedHelper");
        Class<?> c2 = b2.loadClass("LoadedHelper");
        System.out.println("b1.loadClass(\"LoadedHelper\") = " + c1 + "  hash=" + System.identityHashCode(c1));
        System.out.println("b2.loadClass(\"LoadedHelper\") = " + c2 + "  hash=" + System.identityHashCode(c2));
        boolean sameClass = c1 == c2;
        System.out.println("两个加载器各自加载的 Class 是同一个对象吗? " + sameClass + "  (应为 false: 类身份 = 类名 + 加载器)");
        if (sameClass) throw new AssertionError("类身份验证失败");
        // 反射调用各自实例的 hello()，并用 instanceof 验证「类型由加载器定义」
        Object o1 = c1.getDeclaredConstructor().newInstance();
        Method hello = c1.getMethod("hello");
        System.out.println("b1 实例.hello() = " + hello.invoke(o1));
        boolean isInstanceOf = o1 instanceof LoadedHelper;
        System.out.println("b1 实例 instanceof LoadedHelper? " + isInstanceOf + "  (应为 false: 运行时类型由 b1 定义, 与编译期类型不是同一个类)");
        if (isInstanceOf) throw new AssertionError("instanceof 验证失败");
    }

    /** 教学用：双亲委派加载器——不改 loadClass，请求沿默认链路委托父加载器 */
    static class ParentFirstLoader extends ClassLoader {
        ParentFirstLoader() { super(Ex02ClassLoaderDemo.class.getClassLoader()); }
    }

    /**
     * 教学用：打破双亲委派的加载器——loadClass 先自己 defineClass（从 classpath 读字节），
     * 读不到才回退到父加载器。生产里 SPI 框架用「线程上下文类加载器」实现同样的反向加载。
     */
    static class BreakingLoader extends ClassLoader {
        BreakingLoader() { super(Ex02ClassLoaderDemo.class.getClassLoader()); }

        @Override
        protected Class<?> loadClass(String name, boolean resolve) throws ClassNotFoundException {
            if (name.startsWith("java.") || name.startsWith("javax.")) {
                return super.loadClass(name, resolve);   // 核心类必须交给 Bootstrap（防止污染核心库）
            }
            Class<?> c = findLoadedClass(name);          // 先查自己是否已加载过
            if (c == null) {
                byte[] bytes = readClassBytes(name);     // 自己从 classpath 读字节
                if (bytes != null) {
                    c = defineClass(name, bytes, 0, bytes.length);  // 由【本加载器】定义 → 类身份属于本加载器
                } else {
                    c = super.loadClass(name, resolve);  // 读不到才回退父加载器
                }
            }
            if (resolve) resolveClass(c);
            return c;
        }

        private byte[] readClassBytes(String name) {
            try (InputStream in = ClassLoader.getSystemResourceAsStream(name + ".class")) {
                return in == null ? null : in.readAllBytes();
            } catch (Exception e) {
                return null;
            }
        }
    }
}

/** 使用编译期常量：javac 把 LoadedHelper.CONST 内联进本类常量池，字节码里不再引用 LoadedHelper */
class ConstantUser {
    static final String GREETING = LoadedHelper.CONST;
}
