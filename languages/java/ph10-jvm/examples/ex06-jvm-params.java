// examples/ex06-jvm-params.java —— JVM 参数调优观察：进程内读取生效配置 + -Xss 与栈深的关系
// 对应主文档 6. 示例 6：用 -Xms/-Xmx 限制堆后在程序内读到生效值；用不同 -Xss 重跑观察 StackOverflowError 深度
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex06-jvm-params.java
// 运行：java Ex06JvmParams
//       java -Xms64m -Xmx256m -Xss256k Ex06JvmParams      （对比栈深）
//       java -Xms64m -Xmx256m -Xss4m  Ex06JvmParams
// 验证状态：已验证：OpenJDK 17.0.18
// 说明：栈深数字随机器/JIT 时机波动（本机 256k→约 1500、默认→约 4.6 万、4m→约 9.8 万），
//       断言只保证「深度为正」；「栈越大深度越大」的结论由多次运行对比得出, 不设精确数字断言。
import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;

class Ex06JvmParams {
    static int depth = 0;

    public static void main(String[] args) {
        Runtime rt = Runtime.getRuntime();
        System.out.println("JVM       : " + System.getProperty("java.vm.name") + " " + System.getProperty("java.version"));
        System.out.println("启动参数  : " + ManagementFactory.getRuntimeMXBean().getInputArguments());
        System.out.println("堆配置生效: maxMemory=" + mb(rt.maxMemory()) + "MB (对应 -Xmx)"
                + ", totalMemory=" + mb(rt.totalMemory()) + "MB (已申请, 对应 -Xms)"
                + ", freeMemory=" + mb(rt.freeMemory()) + "MB");
        System.out.println("GC 收集器 : " + collectors() + "  (默认 G1, 换 -XX:+UseSerialGC 等后此处会变)");
        System.out.println("可用处理器: " + rt.availableProcessors());

        int d = maxRecursionDepth();
        System.out.println("最大递归深度(触发 StackOverflowError 前) = " + d
                + "  ← 用 -Xss256k / -Xss4m 重跑本程序, 深度随栈增大而增大（数字随机器波动）");
        System.out.println("观察命令: java -Xss256k Ex06JvmParams / java -Xss4m Ex06JvmParams");
        if (d <= 0) throw new AssertionError("递归深度异常");
        System.out.println("自检通过：进程内读取的 JVM 参数与栈深测量完成");
    }

    /** 递归到栈满, 捕获 StackOverflowError 记录深度——每帧消耗约等于栈大小/深度 */
    static int maxRecursionDepth() {
        depth = 0;
        try {
            recurse();
        } catch (StackOverflowError e) {
            return depth;
        }
        return -1;
    }

    static void recurse() {
        depth++;
        recurse();
    }

    static String collectors() {
        StringBuilder sb = new StringBuilder();
        for (GarbageCollectorMXBean b : ManagementFactory.getGarbageCollectorMXBeans()) {
            if (sb.length() > 0) sb.append(" + ");
            sb.append(b.getName());
        }
        return sb.toString();
    }

    static long mb(long bytes) {
        return bytes / 1024 / 1024;
    }
}
