// exercises/sol-02-deadlock-demo.java —— 练习 2 参考实现：必然死锁的两线程程序 + jstack 定位
// 验证环境：OpenJDK 17.0.18；诊断工具 jstack 为 JDK 自带
// 编译：javac sol-02-deadlock-demo.java
// 运行：java DeadlockDemoSol（注意是类名不是文件名；程序将死锁卡住, 供 jstack 诊断）
// 验证状态：已验证：OpenJDK 17.0.18（jstack 实测输出「Found one Java-level deadlock」, 见 README 与下方注释）
// 运行前提：本程序故意死锁（加锁顺序不一致的经典教学演示）, 验证完必须 kill 清理进程
class DeadlockDemoSol {
    static final Object LOCK_A = new Object();
    static final Object LOCK_B = new Object();

    public static void main(String[] args) throws Exception {
        Thread t1 = new Thread(() -> {
            synchronized (LOCK_A) {                    // t1 先拿 A
                sleep(50);                             // 放大窗口: 保证 t2 也拿到 B
                synchronized (LOCK_B) { System.out.println("t1 拿到两把锁"); }
            }
        }, "worker-1");
        Thread t2 = new Thread(() -> {
            synchronized (LOCK_B) {                    // t2 先拿 B
                sleep(50);
                synchronized (LOCK_A) { System.out.println("t2 拿到两把锁"); }
            }
        }, "worker-2");
        t1.start();
        t2.start();
        t1.join();
        t2.join();   // 永远不会走到这: 两个线程互相等待对方释放锁 → 死锁
    }

    // 修复思路（对照练习要求）: 统一加锁顺序——两个线程都「先 A 后 B」即可解除死锁;
    // 或改用 ReentrantLock.tryLock(超时), 拿不到第二把锁就释放已持有的锁
    static void sleep(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }
}
