// examples/ex05-concurrent-collections.java —— 并发集合：ConcurrentHashMap 原子累加/懒加载 + CopyOnWriteArrayList
// 对应主文档 6. 示例 5：merge 原子计数、computeIfAbsent 只初始化一次、CopyOnWriteArrayList 多线程追加不丢不重
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex05-concurrent-collections.java
// 运行：java ConcurrentCollectionsDemo（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

class ConcurrentCollectionsDemo {
    static final int THREADS = 4;
    static final int PER = 1000;

    public static void main(String[] args) throws Exception {
        demoMerge();              // 1. merge：读-改-写合并为一次原子操作，结果确定
        demoComputeIfAbsent();    // 2. computeIfAbsent：并发下初始化逻辑只执行 1 次
        demoCopyOnWrite();        // 3. CopyOnWriteArrayList：多线程追加不丢不重
    }

    /** 4 线程 × 1000 次 merge("hits", 1, Integer::sum)，hits 必为 4000 */
    static void demoMerge() throws Exception {
        ConcurrentHashMap<String, Integer> stats = new ConcurrentHashMap<>();
        runAll(() -> {
            for (int i = 0; i < PER; i++) {
                stats.merge("hits", 1, Integer::sum);   // 原子累加：替代 get+put 两步
            }
        });
        System.out.println("hits = " + stats.get("hits") + "  (期望 " + THREADS * PER + ")");
        if (stats.get("hits") != THREADS * PER) throw new AssertionError("merge 计数丢失");
    }

    /** 100 线程并发 computeIfAbsent 同一 key，初始化逻辑只执行 1 次（懒加载缓存） */
    static void demoComputeIfAbsent() throws Exception {
        AtomicInteger created = new AtomicInteger();
        ConcurrentHashMap<String, String> cache = new ConcurrentHashMap<>();
        runAll(() -> cache.computeIfAbsent("session", k -> {
            created.incrementAndGet();                  // 只应执行一次
            return "exp-" + k;
        }), 100);
        System.out.println("computeIfAbsent 初始化次数 = " + created.get()
                + "  (期望 1), value = " + cache.get("session"));
        if (created.get() != 1) throw new AssertionError("初始化被执行了多次");
    }

    /** 4 线程 × 1000 次 add，size 必为 4000 且无重复（写时复制，读线程不受写影响） */
    static void demoCopyOnWrite() throws Exception {
        CopyOnWriteArrayList<String> listeners = new CopyOnWriteArrayList<>();
        runAll(() -> {
            for (int i = 0; i < PER; i++) listeners.add("handler-" + i);
        });
        Set<String> unique = new HashSet<>(listeners);
        // 4 个线程各加同一批 handler-0..999：总数 4000 不丢，去重 1000，且每个值恰好出现 THREADS 次
        boolean eachOnce = unique.stream().allMatch(s -> Collections.frequency(listeners, s) == THREADS);
        System.out.println("listeners.size = " + listeners.size() + "  (期望 " + THREADS * PER
                + "), 去重后 = " + unique.size() + "  (期望 " + PER + "), 每值出现次数均 = " + THREADS + " : " + eachOnce);
        if (listeners.size() != THREADS * PER || unique.size() != PER || !eachOnce) {
            throw new AssertionError("元素丢失或重复");
        }
    }

    static void runAll(Runnable task) throws Exception {
        runAll(task, THREADS);
    }

    static void runAll(Runnable task, int n) throws Exception {
        Thread[] ts = new Thread[n];
        for (int i = 0; i < n; i++) ts[i] = new Thread(task);
        for (Thread t : ts) t.start();
        for (Thread t : ts) t.join();
    }
}
