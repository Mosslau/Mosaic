// 05 · 内存模型与内置并发原语演示
// 运行：java demos/05_memory_model.java
// 注意：单文件模式运行要求 main 所在类是第一个顶层类，故辅助类型都做成嵌套类

import java.util.concurrent.CountDownLatch;

class MemoryModelDemo {
    static final int THREADS = 8;
    static final int PER_THREAD = 200_000;

    // ---- 辅助类型全部嵌套于此 ----

    static class Counter {
        private int count = 0;
        public synchronized void incr() { count++; }   // 内置锁：互斥 + happens-before
        public synchronized int get()   { return count; }
    }

    // ① 无同步：理论上 THREADS×PER_THREAD，实际因竞态丢更新
    static int raceRun() throws InterruptedException {
        int[] count = {0};                              // 堆上共享，无同步
        CountDownLatch done = new CountDownLatch(THREADS);
        for (int t = 0; t < THREADS; t++) {
            new Thread(() -> {
                for (int i = 0; i < PER_THREAD; i++) count[0]++;  // 非原子读-改-写
                done.countDown();
            }).start();
        }
        done.await();
        return count[0];
    }

    // ② synchronized：结果精确
    static int syncRun() throws InterruptedException {
        Counter c = new Counter();
        CountDownLatch done = new CountDownLatch(THREADS);
        for (int t = 0; t < THREADS; t++) {
            new Thread(() -> {
                for (int i = 0; i < PER_THREAD; i++) c.incr();   // 锁内自增
                done.countDown();
            }).start();
        }
        done.await();
        return c.get();
    }

    // ③ volatile 发布：状态标志安全可见
    static volatile boolean readyFlag = false;
    static volatile int published = -1;
    static int volatileRun() throws InterruptedException {
        readyFlag = false;
        int[] holder = {0};
        Thread reader = new Thread(() -> {
            while (!readyFlag) { /* 自旋等发布 */ }      // volatile 读：见 writer 全部先前写
            holder[0] = published;
        });
        reader.start();
        Thread.sleep(20);                              // 让 reader 先进入自旋
        published = 42;                                // 普通写
        readyFlag = true;                              // volatile 写 → happens-before reader 的读
        reader.join();
        return holder[0];
    }

    // ---- main ----
    public static void main(String[] args) throws InterruptedException {
        System.out.println("== 1. 无同步竞态：8 线程 × " + PER_THREAD + " 次自增 ==");
        int expect = THREADS * PER_THREAD;
        int lost = 0;
        for (int round = 0; round < 5; round++) {
            int got = raceRun();
            if (got < expect) lost++;
            System.out.println("   第 " + (round + 1) + " 轮结果 = " + got
                    + (got < expect ? "   ← 丢失更新！" : "（这轮碰巧没丢）"));
        }
        System.out.println("   5 轮中 " + lost + " 轮 < 预期 " + expect + " ——数据竞争是'不保证'，不是'必然错'");

        System.out.println("\n== 2. synchronized：同样工作量，结果精确 ==");
        System.out.println("   syncRun() = " + syncRun() + "（= 预期 " + expect + "，happens-before 保证）");

        System.out.println("\n== 3. volatile 发布：一个线程安全地把状态交给另一个线程 ==");
        System.out.println("   reader 读到 published = " + volatileRun()
                + "（volatile 写 happens-before volatile 读，普通写也随之可见）");

        System.out.println("\n== 4. 要点 ==");
        System.out.println("   规则：解锁→加锁、volatile 写→读、start/join，是 JMM 的 happens-before 主干；");
        System.out.println("   教训：漏 synchronized 编译器不报错——这正是 Rust Send/Sync 要在编译期拦住的事。");
    }
}
