// examples/ex02-class-loader.java 的配套被加载类 —— public 顶层类，须独立文件
// 本类同时被三个加载器加载演示：AppClassLoader（常规）、ParentFirstLoader（双亲委派）、
// BreakingLoader × 2（打破双亲委派，各 defineClass 一次）。public 保证跨加载器反射可访问。
public class LoadedHelper {
    static final String CONST = "编译期常量";
    static int initCount = 0;
    static {
        initCount++;
        System.out.println(">> LoadedHelper <clinit> 执行 (initCount=" + initCount + ")");
    }
    public String hello() {
        return "hello from " + getClass().getClassLoader().getClass().getSimpleName();
    }
}
