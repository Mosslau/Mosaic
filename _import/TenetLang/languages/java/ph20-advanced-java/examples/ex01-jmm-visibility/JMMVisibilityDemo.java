/*
 * examples/ex01-jmm-visibility/JMMVisibilityDemo.java
 * JMM 可见性/有序性演示：volatile 为什么能解决可见性，非 volatile 共享标志为什么「可能」看不见。
 *
 * ⚠️ 教学故意示例（部分代码是「错误写法」的演示，不是正确示例）：
 *   Phase 1（buggy）使用非 volatile 共享标志，读者线程可能在标志已被写后仍看不到新值——
 *   这是未定义行为，是否复现取决于 CPU 架构 / JIT 优化程度 / 线程调度，**不确定必现**。
 *   本机（OpenJDK 17.0.18 / macOS ARM64 / 解释模式 -Xint 与 JIT 各试）均**未放大出**该现象：
 *   reader 都在约 7 千万次自旋内退出——不要因此以为 bug 不存在，这只说明该环境没有把
 *   「缓存未失效」的窗口拉长；换旧 JDK、x86 强内存序机器或换一种循环写法就可能复现。
 *   Phase 2/3 是正确写法，行为确定。
 *
 * 验证环境：OpenJDK 17.0.18（Homebrew）/opt/homebrew/opt/openjdk@17
 * 编译：javac -encoding UTF-8 -d /tmp/tl20-cls JMMVisibilityDemo.java
 * 运行：java -cp /tmp/tl20-cls JMMVisibilityDemo            （JIT 模式）
 * 运行：java -Xint -cp /tmp/tl20-cls JMMVisibilityDemo      （解释模式，更容易放大可见性问题）
 * 本机已实测：javac 17.0.18 编译通过，两种模式均可运行；Phase 1 在本机未复现（见上），Phase 2/3 PASS
 */
public class JMMVisibilityDemo {

    private static boolean stop = false;          // 故意：非 volatile（Phase 1 的错误写法）
    private static volatile boolean vStop = false; // Phase 2 的正确写法
    private static int shared = 0;                // 工作线程写入，主线程 Phase 3 读取

    public static void main(String[] args) throws InterruptedException {
        phase1BuggyFlag();
        phase2VolatileFix();
        phase3HappensBeforeOfSynchronized();
        System.out.println("ALL DONE");
    }

    /** Phase 1（故意错误写法，仅观察）：非 volatile 标志 + 忙循环读者。
     *  读者把 stop 读进寄存器/缓存后可能一直用旧值，写者线程永远叫不停它。 */
    private static void phase1BuggyFlag() throws InterruptedException {
        Thread reader = new Thread(() -> {
            long spins = 0;
            while (!stop) {            // 热点循环内无任何同步点 → 编译器/CPU 可能只读一次
                spins++;
            }
            System.out.println("PASS? reader exit after " + spins + " spins (stop became visible)");
        }, "reader-buggy");
        reader.start();
        Thread.sleep(300);             // 让读者进入循环
        new Thread(() -> stop = true, "writer-buggy").start();

        // watchdog：2 秒后若 reader 仍没退，说明可见性未保证（本环境观察到的现象）
        Thread watchdog = new Thread(() -> {
            try {
                Thread.sleep(2000);
            } catch (InterruptedException ignored) {
                return;
            }
            System.out.println("OBSERVED: reader still spinning after 2s — non-volatile flag NOT visible. "
                    + "(This is exactly the JMM problem; outcome is env-dependent)");
            System.exit(0);            // 结束整个程序，避免无限挂起；运行前提见文件头
        }, "watchdog");
        watchdog.setDaemon(true);
        watchdog.start();
        reader.join(3000);
        if (reader.isAlive()) {
            System.out.println("OBSERVED: reader alive after 3s — bug reproduced in this run");
            System.exit(0);
        }
        System.out.println("Note: reader exited quickly on this run (visibility happened to work here)");
    }

    /** Phase 2（正确写法）：volatile 保证写后对其他线程立即可见（JMM: volatile 写-读是 happens-before）。 */
    private static void phase2VolatileFix() throws InterruptedException {
        stop = false;                                // 注意：主线程写的普通字段……
        vStop = false;
        Thread writer = new Thread(() -> {
            sleepQuietly(200);
            shared = 42;                             // 普通写
            vStop = true;                            // volatile 写：之前的一切普通写都会「随它一起发布」
        }, "writer-volatile");
        Thread reader = new Thread(() -> {
            while (!vStop) {                         // volatile 读
                Thread.onSpinWait();
            }
            System.out.println("PASS: reader saw vStop=true; shared=" + shared
                    + " (42 proves volatile 写同步释放了之前的所有普通写)");
        }, "reader-volatile");
        writer.start();
        reader.start();
        writer.join();
        reader.join();
    }

    /** Phase 3：synchronized 的 happens-before（同一把锁的 unlock → 之后的 lock）语义演示。 */
    private static void phase3HappensBeforeOfSynchronized() throws InterruptedException {
        Object lock = new Object();
        int[] data = new int[1];                       // 数组元素共享可变
        Thread writer = new Thread(() -> {
            synchronized (lock) {                      // 先拿到锁
                sleepQuietly(200);                     // 持锁期间 sleep：迫使主线程在锁外排队
                data[0] = 7;                           // 临界区内写
            }                                          // 退出锁 = unlock（data 写入随之「发布」）
        }, "writer-sync");
        writer.start();
        sleepQuietly(50);                              // 让 writer 先进锁
        synchronized (lock) { }                        // acquire 同一把锁：必然排在 writer 之后 →
        System.out.println("PASS: after acquiring same lock, data[0]=" + data[0]
                + " (synchronized 的 unlock→lock 构成 happens-before，写必可见)");
        writer.join();
    }

    private static void sleepQuietly(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
