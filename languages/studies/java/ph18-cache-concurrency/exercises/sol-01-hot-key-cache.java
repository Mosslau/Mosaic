// exercises/sol-01-hot-key-cache.java —— 练习 1 参考实现：热点数据缓存（roadmap ph18 练习：热点数据缓存）
// 目标还原（见 exercises/README.md）：两级读缓存（本地 L1 + 远端 L2）+ 单飞重建 + 热点 key 识别。
//   生产对应：L1=Caffeine（主文档 3.2/ex07）、L2=Redis（3.1/3.3）、单飞=3.3 击穿解法、热点识别=3.3 热点保护。
// 实现要点：
//   - 读路径：L1 → L2 → DB（Cache-Aside）；回填逐级写。
//   - 单飞：并发 miss 同 key 时只有 1 个线程回源（per-key monitor 双检），DB 访问次数可断言。
//   - 热点识别：滑动时间窗内访问数 ≥ hotAfter 即标记为热点 key（本参考实现提供 isHot 供演示与输出；
//     生产上热点 key 的下一步是针对性保护：单独更短 TTL、本地独立副本、防雪崩抖动等，见主文档 3.3）。
// 教学性覆盖：L1/L2 用 ConcurrentHashMap 自实现（语义同 ex07；不引 Caffeine 依赖保持单文件可 javac）；
//             时间用虚拟时钟，无 sleep —— 断言确定可复现。
// 验证环境：OpenJDK 17（javac -version -> 17.x）；无第三方依赖
// 验证命令：
//   # 1. 编译（在 exercises/ 目录下执行）
//   javac sol-01-hot-key-cache.java
//   # 2. 运行
//   java HotKeyCacheDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：javac 编译通过、运行全部 PASS）

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/** 热点数据缓存练习参考实现：两级缓存 + 单飞 + 热点识别 */
final class HotKeyCacheDemo {

    interface Clock {
        long now();
    }

    static final class ManualClock implements Clock {
        private long t;

        ManualClock(long start) {
            this.t = start;
        }

        void advance(long ms) {
            t += ms;
        }

        @Override
        public long now() {
            return t;
        }
    }

    /** 假数据源（DB）：key 存在即返回，loads 计次 */
    interface Source {
        String load(String key);
    }

    static final class CountingSource implements Source {
        private final java.util.Set<String> rows;
        final AtomicInteger loads = new AtomicInteger();

        CountingSource(String... rows) {
            this.rows = java.util.Set.of(rows);
        }

        @Override
        public String load(String key) {
            loads.incrementAndGet();
            return rows.contains(key) ? "value:" + key : null;
        }
    }

    /** 带 TTL 的条目存储（L1/L2 共用的小型容器） */
    static final class TtlStore {
        record Entry(String value, long expiresAt) {
        }

        private final Clock clock;
        private final Map<String, Entry> map = new ConcurrentHashMap<>();

        TtlStore(Clock clock) {
            this.clock = clock;
        }

        String get(String key) {
            Entry e = map.get(key);
            if (e == null || e.expiresAt <= clock.now()) {
                return null;
            }
            return e.value;
        }

        void put(String key, String value, long ttlMs) {
            map.put(key, new Entry(value, clock.now() + ttlMs));
        }
    }

    /** 热点数据缓存：L1(本地) + L2(远端) + 单飞回源 + 热点识别 */
    static final class HotKeyCache {
        private static final int HOT_WINDOW_MS = 1_000;   // 热点判定窗口
        private final Clock clock;
        private final Source source;
        private final TtlStore l1;
        private final TtlStore l2;
        private final Map<String, Object> monitors = new ConcurrentHashMap<>(); // 单飞锁
        private final Map<String, Deque<Long>> accessTimes = new ConcurrentHashMap<>();
        private final Map<String, Boolean> hotKeys = new ConcurrentHashMap<>();
        private final long l1TtlMs;
        private final long l2TtlMs;
        private final int hotAfter; // 窗口内访问多少次算热点

        HotKeyCache(Clock clock, Source source, long l1TtlMs, long l2TtlMs, int hotAfter) {
            this.clock = clock;
            this.source = source;
            this.l1 = new TtlStore(clock);
            this.l2 = new TtlStore(clock);
            this.l1TtlMs = l1TtlMs;
            this.l2TtlMs = l2TtlMs;
            this.hotAfter = hotAfter;
        }

        String read(String key) {
            String v = l1.get(key);
            if (v != null) {
                recordAccess(key);
                return v;
            }
            return readSingleFlight(key); // miss 统一走单飞，防并发击穿
        }

        /** 单飞 + 双检：同 key 并发缺失只允许一个线程回源并回填两级缓存 */
        private String readSingleFlight(String key) {
            Object monitor = monitors.computeIfAbsent(key, k -> new Object());
            synchronized (monitor) {
                String v = l1.get(key);   // 双检 L1
                if (v != null) {
                    recordAccess(key);
                    return v;
                }
                v = l2.get(key);          // 再查 L2
                if (v != null) {
                    l1.put(key, v, l1TtlMs);
                    recordAccess(key);
                    return v;
                }
                v = source.load(key);     // 两级都 miss：真正回源（本练习的并发关键点）
                if (v != null) {
                    l2.put(key, v, l2TtlMs);
                    l1.put(key, v, l1TtlMs);
                }
                monitors.remove(key);      // 必须在回填后移除（参照 ex03/ex06 的同一约定）
                recordAccess(key);
                return v;
            }
        }

        /** 记录一次访问并判定热点（滑动窗口：只保留最近 HOT_WINDOW_MS 的访问） */
        private void recordAccess(String key) {
            long now = clock.now();
            Deque<Long> deque = accessTimes.computeIfAbsent(key, k -> new ArrayDeque<>());
            synchronized (deque) {
                while (!deque.isEmpty() && deque.peekFirst() <= now - HOT_WINDOW_MS) {
                    deque.pollFirst();
                }
                deque.addLast(now);
                if (deque.size() >= hotAfter) {
                    hotKeys.putIfAbsent(key, true); // 首个窗口命中即标记，后续不重复置位
                }
            }
        }

        boolean isHot(String key) {
            return hotKeys.containsKey(key);
        }
    }

    static void check(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError("自检失败: " + label);
        }
        System.out.println("PASS  " + label);
    }

    public static void main(String[] args) throws InterruptedException {
        System.out.println("场景一：并发 miss 单飞 —— 热点 key 冷启动，16 线程同时读只回源 1 次");
        ManualClock clock = new ManualClock(0);
        CountingSource source = new CountingSource("hot:item");
        HotKeyCache cache = new HotKeyCache(clock, source, 5_000, 60_000, 10);
        ExecutorService pool = Executors.newFixedThreadPool(16);
        CountDownLatch start = new CountDownLatch(1);
        CountDownLatch done = new CountDownLatch(16);
        AtomicInteger allSame = new AtomicInteger();
        for (int i = 0; i < 16; i++) {
            pool.submit(() -> {
                try {
                    start.await();
                    if ("value:hot:item".equals(cache.read("hot:item"))) {
                        allSame.incrementAndGet();
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                } finally {
                    done.countDown();
                }
            });
        }
        start.countDown();
        done.await(10, TimeUnit.SECONDS);
        pool.shutdownNow();
        check(source.loads.get() == 1, "16 线程并发读同一冷 key → DB 只回源 1 次（单飞防击穿）");
        check(allSame.get() == 16, "16 个线程拿到的结果一致（等待者共享回源结果）");

        System.out.println("场景二：两级缓存生效 —— 后续大量读全部命中，不再碰 DB");
        for (int i = 0; i < 200; i++) {
            cache.read("hot:item");
        }
        check(source.loads.get() == 1, "200 次串行读全部命中缓存（L1 或 L2），DB 访问仍是 1 次");

        System.out.println("场景三：两级 TTL —— L1 先过期时 L2 兜底，两级都过期才回源");
        clock.advance(6_000); // L1 ttl=5s 过期，L2 ttl=60s 未过期
        cache.read("hot:item");
        check(source.loads.get() == 1, "L1 过期但 L2 还在：命中 L2 → 不碰 DB");
        clock.advance(55_000); // L2 ttl=60s 也过期
        cache.read("hot:item");
        check(source.loads.get() == 2, "两级都过期后回到 DB（TTL 到期重读是常态，要靠单飞防并发击穿）");

        System.out.println("场景四：热点识别 —— 窗口内访问量超阈值被标记，便于后续针对性保护");
        check(cache.isHot("hot:item"), "hot:item 已被标记为热点（此前访问量远超阈值）");
        ManualClock clock2 = new ManualClock(0);
        CountingSource source2 = new CountingSource("cold:item");
        HotKeyCache cold = new HotKeyCache(clock2, source2, 5_000, 60_000, 10);
        for (int i = 0; i < 3; i++) {
            cold.read("cold:item"); // 3 次 < 阈值 10
        }
        check(!cold.isHot("cold:item"), "低访问 key 不标记（3 次 < 阈值 10，避免误伤长尾数据）");

        System.out.println();
        System.out.println("全部自检通过。对照主文档 3.3/3.2 与 exercises/README：");
        System.out.println("  - 两级读缓存把压力挡在 L1/L2，回源（DB）是最后一道；单飞保证并发 miss 不击穿");
        System.out.println("  - 生产 L1 换 Caffeine（见 ex02/ex07），L2 换 Redis（ex01），回源处记得空值缓存（穿透）");
        System.out.println("  - 热点识别只是起点：识别后要做的保护（短 TTL、独立副本、预加载）见主文档 3.3 热点保护");
    }
}
