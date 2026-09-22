// project/memory-leak-lab.java —— 内存泄漏实验台：3 种典型泄漏 + 对照组，配合 jstat/jmap/堆 dump 诊断
// 对应 Roadmap「ph10 JVM 阶段」推荐项目「内存泄漏 demo」（实现 2-3 种典型泄漏并给出诊断路径）
// 验证环境：OpenJDK 17.0.18（默认 G1）；诊断工具 jps/jstat/jmap/jcmd 为 JDK 自带
// 编译：javac memory-leak-lab.java
// 运行：java -Xms256m -Xmx256m MemoryLeakLab static 60
//       java -Xms256m -Xmx256m MemoryLeakLab threadlocal 60
//       java -Xms256m -Xmx256m MemoryLeakLab conn 60
//       java -Xms256m -Xmx256m MemoryLeakLab clean 60
// 验证状态：已验证：OpenJDK 17.0.18（三种泄漏模式 jmap -histo 均见 byte[] 异常突出; clean 模式不 OOM 正常结束）
// 运行前提：泄漏模式故意泄漏仅供诊断练习, 验证完 kill 清理进程与 hprof
import java.lang.management.ManagementFactory;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

class MemoryLeakLab {

    public static void main(String[] args) throws Exception {
        String mode = args.length > 0 ? args[0] : "static";
        int capMB = args.length > 1 ? Integer.parseInt(args[1]) : 60;
        long pid = ProcessHandle.current().pid();
        System.out.println("模式 = " + mode + ", 目标 = " + capMB + " MB, pid = " + pid);
        System.out.println("启动参数: " + ManagementFactory.getRuntimeMXBean().getInputArguments());

        switch (mode) {
            case "static"      -> runLeak("static", capMB, () -> leakStatic(1));
            case "threadlocal" -> runLeak("threadlocal", capMB, () -> leakThreadLocal());
            case "conn"        -> runLeak("conn", capMB, () -> leakConn(1));
            case "clean"       -> runClean();
            default -> throw new IllegalArgumentException("未知模式: " + mode
                    + "（可选 static / threadlocal / conn / clean）");
        }
    }

    /** 通用泄漏骨架：每轮分配 1MB 直到 capMB, 保持存活约 60 秒供诊断, 然后继续分配直至 OOM */
    static void runLeak(String name, int capMB, Runnable allocOneMb) throws Exception {
        int i = 0;
        while (true) {
            allocOneMb.run();
            i++;
            if (i % 10 == 0) {
                System.out.println("[" + name + "] 已累计 " + i + " MB (进程存活)");
            }
            if (i >= capMB) {
                System.out.println("[" + name + "] 达到 " + capMB + " MB, 保持存活约 60 秒供诊断"
                        + "（jstat -gcutil / jmap -histo / jmap -dump / jcmd GC.heap_dump）…");
                for (int s = 0; s < 60; s++) Thread.sleep(1000);
                System.out.println("[" + name + "] 继续分配, 即将 OOM…");
            }
            Thread.sleep(30);
        }
    }

    /** 泄漏 1：静态集合持续 add —— 静态字段是 GC Root, 对象永远可达 */
    static final List<byte[]> STATIC_CACHE = new ArrayList<>();
    static void leakStatic(int mb) {
        STATIC_CACHE.add(new byte[mb * 1024 * 1024]);
    }

    /** 泄漏 2：ThreadLocal 不 remove + 线程池 —— 每个任务新建一个 ThreadLocal 并塞 1MB,
     *  不 remove: 任务结束后值仍被工作线程的 ThreadLocalMap 持有, 线程不销毁 → 泄漏累积 */
    static final ExecutorService POOL = Executors.newFixedThreadPool(8, r -> {
        Thread t = new Thread(r, "leak-worker");
        t.setDaemon(true);
        return t;
    });
    static void leakThreadLocal() {
        POOL.submit(() -> {
            ThreadLocal<byte[]> tl = new ThreadLocal<>();   // 每任务一个全新 key
            tl.set(new byte[1024 * 1024]);                  // 1MB 值, 故意不 remove
            // 真实工程里对应: 请求上下文/连接信息用 ThreadLocal 存了大对象, finally 里忘了 remove
        });
    }

    /** 泄漏 3：连接/IO 未关闭（模拟）——「打开」的连接持有 1MB 缓冲且永不 close,
     *  被静态开放列表持有 → 句柄与内存双泄漏的简化模型 */
    static final List<FakeConnection> OPEN_CONNECTIONS = new ArrayList<>();
    static void leakConn(int mb) {
        OPEN_CONNECTIONS.add(new FakeConnection(mb));
    }
    static class FakeConnection {
        final byte[] buffer = new byte[1024 * 1024];       // 每个连接 1MB 缓冲
        FakeConnection(int mb) { /* 模拟打开连接: 分配资源 */ }
        void close() { /* 模拟关闭: 释放资源——本 demo 永不调用, 正是泄漏点 */ }
    }

    /** 对照组：同样分配 1MB 但立即释放引用 → 堆稳定, 正常结束不 OOM */
    static void runClean() throws Exception {
        System.out.println("[clean] 对照: 每轮分配 1MB 后立即丢弃引用, 共 300 轮");
        long total = 0;
        for (int i = 0; i < 300; i++) {
            byte[] tmp = new byte[1024 * 1024];             // 局部变量, 每轮结束即可回收
            total += tmp.length;
            if (i % 100 == 0) System.out.println("[clean] 第 " + i + " 轮, 累计分配 " + (total / 1048576) + " MB");
        }
        System.out.println("[clean] 300 轮完成, 无 OOM —— 泄漏模式与它的差别只在「引用是否被长期持有」");
    }
}
