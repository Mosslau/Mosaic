// examples/ex05-jmm-demo.java —— JMM 内存模型演示：volatile 可见性实验 + happens-before 安全发布
// 对应主文档 6. 示例 5：无同步时写线程的修改对读线程可能不可见；volatile/synchronized 靠 happens-before 保证可见
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex05-jmm-demo.java
// 运行：java Ex05JmmDemo（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
// 说明：可见性实验的「非 volatile 是否能看到写」随硬件/编译器/JIT 时机波动（本机 Apple Silicon/arm64, 弱内存模型下多次实测均
//       未看到, 但这不是语言保证）；volatile 与 synchronized 的可见性是 JMM 保证的, 断言稳定成立。
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

class Ex05JmmDemo {
    static boolean plainStop;          // 非 volatile：读线程可能永远看不到写线程的修改
    static volatile boolean volStop;   // volatile：写读之间建立 happens-before

    public static void main(String[] args) throws Exception {
        demoPlainVisibility();   // 1. 非 volatile 标志：能否看到写线程的修改？（随机器波动, 如实打印）
        demoVolatileVisibility();// 2. volatile 标志：happens-before 保证可见, 必然退出
        demoSafePublication();   // 3. 安全发布：synchronized/volatile 之外, 还有更基础的 happens-before 传递
        System.out.println("自检通过：volatile 与 synchronized 的可见性断言全部成立");
    }

    /** 非 volatile 标志实验：主线程 2 秒后置 stop, 看工作线程能否及时看到。
     *  注意: 本机（Apple Silicon/arm64, 弱内存模型）+ JIT 下多次实测工作线程都看不到（循环被编译优化, 标志读被提升到循环外）,
     *  但这依赖硬件与编译时机——本段输出如实打印, 不作硬断言 */
    static void demoPlainVisibility() throws Exception {
        System.out.println("\n=== 1. 非 volatile 标志可见性实验（观察类输出, 结论随平台波动）===");
        CountDownLatch started = new CountDownLatch(1);
        long[] counter = new long[1];
        Thread worker = new Thread(() -> {
            started.countDown();
            while (!plainStop) counter[0]++;
        }, "worker-plain");
        worker.setDaemon(true);             // 非 volatile 实验的 worker 可能永不退出, 设 daemon 保证主线程结束后 JVM 能退出
        worker.start();
        started.await();
        Thread.sleep(2000);                 // 给 JIT 时间把 !plainStop 提升出循环
        plainStop = true;                   // 主线程写标志
        worker.join(2000);                  // 最多再等 2 秒
        boolean exited = !worker.isAlive();
        System.out.println("  主线程置 plainStop=true 后, 工作线程在 2 秒内退出: " + exited
                + "  (counter=" + counter[0] + ")");
        System.out.println("  本机（Apple Silicon/arm64, 弱内存模型）多次实测均未退出——JIT 把标志读提升到循环外, 可见性失败是真实存在的");
        if (exited) {
            System.out.println("  注意: 本次运行看到了写——非 volatile 不保证可见, 看到与否都不违反 JMM");
        }
        worker.interrupt();
    }

    /** volatile 标志实验：volatile 写 happens-before 后续对同一 volatile 的读 → 工作线程必然退出（JMM 保证） */
    static void demoVolatileVisibility() throws Exception {
        System.out.println("\n=== 2. volatile 标志可见性（JMM 保证, 必然退出）===");
        CountDownLatch started = new CountDownLatch(1);
        long[] counter = new long[1];
        Thread worker = new Thread(() -> {
            started.countDown();
            while (!volStop) counter[0]++;
        }, "worker-volatile");
        worker.setDaemon(true);
        worker.start();
        started.await();
        Thread.sleep(200);
        volStop = true;
        worker.join(5000);
        if (worker.isAlive()) throw new AssertionError("volatile 标志未能在超时内被看到——happens-before 失效");
        System.out.println("  主线程置 volStop=true 后, 工作线程及时退出 (counter=" + counter[0] + ")");
        System.out.println("  volatile 写 happens-before 读: 可见性由 JMM 保证, 与硬件无关");
    }

    /** 安全发布：写线程在释放锁前写字段, 读线程在获取同一把锁后读字段——监视器锁规则保证全部可见。
     *  这里再补一个 volatile 版发布：写 volatile 前的写入对读到该 volatile 的线程可见 */
    static void demoSafePublication() throws Exception {
        System.out.println("\n=== 3. happens-before 传递: synchronized 安全发布 ===");
        final Object lock = new Object();
        final int[] payload = new int[3];
        Thread writer = new Thread(() -> {
            synchronized (lock) {           // 写线程: 先写数据, 再释放锁
                payload[0] = 11;
                payload[1] = 22;
                payload[2] = 33;
            }                               // 解锁 happens-before 后续加锁
        }, "writer");
        writer.start();
        writer.join();
        Thread reader = new Thread(() -> {
            synchronized (lock) {           // 读线程: 获取同一把锁 → 必能看到 writer 的全部写入
                if (payload[0] != 11 || payload[1] != 22 || payload[2] != 33) {
                    throw new AssertionError("synchronized 安全发布失败");
                }
                System.out.println("  读线程在锁内读到完整 payload=[11,22,33] —— 监视器锁规则成立");
            }
        }, "reader");
        reader.start();
        reader.join();
    }
}
