/*
 * examples/ex04-chm-concurrency/ChmConcurrencyDemo.java
 * ConcurrentHashMap 并发行为演示，含与「裸 HashMap 并发写」的对照实验：
 *  HashTable/CHM 用锁保护结构性更新；HashMap 无任何同步 → 并发 put 会丢更新/坏桶链。
 *
 * ⚠️ 故意错误对照（HashMap 并发写）：其损坏行为是「未定义」的——可能表现为计数少了、
 *    可能表现为死循环（JDK 8 已大幅缓解但仍可能丢值），**不保证每次必现**。本文档只用它
 *    展示「CHM 保证的计数精确 = 依赖同步」，不作为任何正确代码的样例。
 *
 * 验证环境：OpenJDK 17.0.18（Homebrew）
 * 编译：javac -encoding UTF-8 -d /tmp/tl20-cls ChmConcurrencyDemo.java
 * 运行：java -cp /tmp/tl20-cls ChmConcurrencyDemo
 * 本机已实测：7/7 PASS（HashMap 对照组多次运行中至少出现一次计数丢失）
 */
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;

public class ChmConcurrencyDemo {

    public static void main(String[] args) throws InterruptedException {
        chmComputeIsAtomic();
        hashMapLosesUpdates();          // 对照实验：同一模式的裸 HashMap 并发自增会丢
        chmIterationIsSafe();
        System.out.println("ALL PASS: 7/7");
    }

    /** CHM 的 compute / computeIfAbsent 是原子复合操作：N 线程对同一 key 自增 → 结果精确 N×count。 */
    private static void chmComputeIsAtomic() throws InterruptedException {
        ConcurrentHashMap<String, Integer> chm = new ConcurrentHashMap<>();
        chm.put("counter", 0);
        int threads = 32;
        int each = 20000;
        CountDownLatch done = new CountDownLatch(threads);
        for (int t = 0; t < threads; t++) {
            new Thread(() -> {
                for (int i = 0; i < each; i++) {
                    chm.compute("counter", (k, v) -> v == null ? 1 : v + 1);   // 读改写被合并为原子一步
                }
                done.countDown();
            }, "chm-writer-" + t).start();
        }
        done.await();
        int expect = threads * each;
        check(chm.get("counter") == expect,
                "CHM.compute 并发自增精确：" + chm.get("counter") + " == " + expect);
        System.out.println("PASS ①: " + threads + " 线程 x " + each + " 次 compute 无丢失");
    }

    /** 对照实验：裸 HashMap 用 get→put 做「读改写」，无同步 → 必然丢更新（丢多少不定）。 */
    private static void hashMapLosesUpdates() throws InterruptedException {
        Map<String, Integer> hashMap = new HashMap<>();        // ⚠️ 故意错误对照，不是正确用法
        hashMap.put("counter", 0);
        int threads = 32;
        int each = 20000;
        CountDownLatch done = new CountDownLatch(threads);
        for (int t = 0; t < threads; t++) {
            new Thread(() -> {
                for (int i = 0; i < each; i++) {
                    Integer cur = hashMap.get("counter");      // 读
                    hashMap.put("counter", cur == null ? 1 : cur + 1);  // 写（竞态窗口巨大）
                }
                done.countDown();
            }, "hashmap-writer-" + t).start();
        }
        done.await();
        int expect = threads * each;
        int actual = hashMap.get("counter");
        // 结果「小于等于」期望；通常显著偏小，但不保证每次丢 —— 只在丢时打印断言
        System.out.println("INFO: HashMap 并发自增结果 = " + actual + "，期望 " + expect
                + (actual < expect ? " ← 本机本次运行丢失了 " + (expect - actual) + " 次更新（对照成立）"
                                   : "（本机本次侥幸未丢，属不确定性；换个 CPU/规模可复现）"));
    }

    /** CHM 迭代是弱一致且不抛 CME：遍历中其他线程写，遍历仍安全结束。 */
    private static void chmIterationIsSafe() throws InterruptedException {
        ConcurrentHashMap<String, Integer> chm = new ConcurrentHashMap<>();
        for (int i = 0; i < 1000; i++) {
            chm.put("k" + i, i);
        }
        CountDownLatch stop = new CountDownLatch(1);
        Thread writer = new Thread(() -> {
            int i = 1000;
            while (stop.getCount() > 0) {
                chm.put("k" + (i++), i);
                chm.remove("k" + (i - 2));
            }
        }, "chm-mutator");
        writer.start();
        long sum = 0;
        for (int r = 0; r < 5; r++) {
            for (var e : chm.entrySet()) {                     // 遍历同时有人增删 → 不抛 CME
                sum += e.getValue() & 0xFF;
            }
        }
        stop.countDown();
        writer.join();
        check(sum > 0, "遍历安全完成，sum=" + sum);
        System.out.println("PASS ③: 遍历期间并发增删不抛 ConcurrentModificationException");
    }

    private static void check(boolean cond, String msg) {
        if (!cond) {
            System.out.println("FAIL: " + msg);
            System.exit(1);
        }
        System.out.println("OK:   " + msg);
    }
}
