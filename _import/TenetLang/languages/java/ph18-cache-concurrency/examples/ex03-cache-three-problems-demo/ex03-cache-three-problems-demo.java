// examples/ex03-cache-three-problems-demo/ex03-cache-three-problems-demo.java
// 缓存穿透 / 击穿 / 雪崩 的成因与防护模拟（对应主文档 3.3）
// 教学映射：
//   穿透 = 查一个「数据库里就不存在」的 key，缓存永远挡不住 → 每次请求都打到 DB。
//         解法一：缓存空值（带较短 TTL）；解法二：布隆过滤器在缓存前先挡（见主文档 3.3 对比表）。
//   击穿 = 单个「热点 key」过期瞬间，大量并发请求同时 miss 回源 → 解法：互斥重建/单飞（single-flight）。
//   雪崩 = 大量 key 同一时刻集体过期，DB 被单波回源打满 → 解法：TTL 加随机抖动、多级缓存、限流兜底。
// 设计：一个带虚拟时钟与懒过期的 CacheAside 引擎 + 三个开关（cacheNull / singleFlight / jitter）
//       分别演示三个问题的「有防护 vs 无防护」；击穿场景用真实多线程 + 闩锁把竞态做确定可断言。
// 教学性覆盖：缓存载体是 ConcurrentHashMap（生产是 Caffeine/Redis，见 examples/ex02/ex07）；
//             布隆过滤器只讲思路不实现；DB 的「耗时」用闩锁人为制造，只为把并发竞态固定下来。
// 验证环境：OpenJDK 17（javac -version -> 17.x）；无第三方依赖
// 验证命令：
//   # 1. 编译（在 examples/ex03-cache-three-problems-demo/ 目录下执行）
//   javac ex03-cache-three-problems-demo.java
//   # 2. 运行
//   java CacheThreeProblemsDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：javac 编译通过、运行全部 PASS）

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/** 缓存三兄弟：穿透 / 击穿 / 雪崩 演示 */
final class CacheThreeProblemsDemo {

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

    /** 数据源 = 数据库（教学简化：只关心被访问了多少次、key 是否存在） */
    interface DataSource {
        String load(String key); // null = DB 里没有这个 key
    }

    /** 带访问计数的数据源 */
    static final class CountingDataSource implements DataSource {
        private final Set<String> rows;
        final AtomicInteger loads = new AtomicInteger();

        CountingDataSource(String... existingKeys) {
            this.rows = Set.of(existingKeys);
        }

        @Override
        public String load(String key) {
            loads.incrementAndGet();
            return rows.contains(key) ? "value:" + key : null;
        }
    }

    /**
     * 可开关的 CacheAside 引擎，三个开关对应三个防护：
     *   cacheNull    = 缓存空值（挡穿透）
     *   singleFlight = 单飞：同一 key 的并发缺失只允许一个线程回源重建（挡击穿）
     *   jitterMs     = 写入 TTL 加 [0, jitterMs) 随机抖动（挡雪崩）
     */
    static final class CacheAside {
        record Entry(String value, long expiresAt) {
        }

        private final Clock clock;
        private final DataSource source;
        private final long ttlMs;
        private final boolean cacheNull;
        private final boolean singleFlight;
        private final long jitterMs;
        private final Map<String, Entry> map = new ConcurrentHashMap<>();
        private final Map<String, Object> monitors = new ConcurrentHashMap<>();

        CacheAside(Clock clock, DataSource source, long ttlMs,
                   boolean cacheNull, boolean singleFlight, long jitterMs) {
            this.clock = clock;
            this.source = source;
            this.ttlMs = ttlMs;
            this.cacheNull = cacheNull;
            this.singleFlight = singleFlight;
            this.jitterMs = jitterMs;
        }

        String get(String key) {
            if (singleFlight) {
                return getSingleFlight(key);
            }
            long now = clock.now();
            Entry e = map.get(key);
            if (e != null && e.expiresAt > now) {
                return e.value; // 缓存命中
            }
            return reload(key, now);
        }

        /** 单飞：per-key monitor 串行化「查缺失 → 回源 → 回填」，后来的线程双检命中，不重复打 DB */
        private String getSingleFlight(String key) {
            Object monitor = monitors.computeIfAbsent(key, k -> new Object());
            synchronized (monitor) {
                long now = clock.now();
                Entry e = map.get(key);
                if (e != null && e.expiresAt > now) {
                    return e.value; // 双检：等待期间别人已回填
                }
                String v = reload(key, now);
                monitors.remove(key); // 必须在回填之后移除，否则后来者会绕过双检再打一次 DB
                return v;
            }
        }

        private String reload(String key, long now) {
            String v = source.load(key);
            if (v != null || cacheNull) { // 空值防护开启时才把 null 也缓存
                long jitter = jitterMs == 0 ? 0 : (key.hashCode() & Integer.MAX_VALUE) % jitterMs;
                map.put(key, new Entry(v, now + ttlMs + jitter));
            }
            return v;
        }
    }

    static void check(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError("自检失败: " + label);
        }
        System.out.println("PASS  " + label);
    }

    public static void main(String[] args) throws Exception {
        // ------------------------------------------------------------------
        // 场景 A：缓存穿透 —— DB 不存在的 key 缓存存不下，每次请求都穿透到 DB
        // ------------------------------------------------------------------
        System.out.println("场景 A：缓存穿透（key 在 DB 里不存在 → 缓存永远 miss）");
        ManualClock ca = new ManualClock(0);
        CountingDataSource dbA1 = new CountingDataSource("user:1", "user:2");
        CacheAside naiveA = new CacheAside(ca, dbA1, 60_000, false, false, 0);
        for (int i = 0; i < 50; i++) {
            naiveA.get("user:missing");
        }
        check(dbA1.loads.get() == 50, "无防护：50 次请求 = 50 次 DB 访问（不存在的数据怎么都缓存不了）");
        CountingDataSource dbA2 = new CountingDataSource("user:1", "user:2");
        CacheAside guardA = new CacheAside(ca, dbA2, 60_000, true, false, 0);
        for (int i = 0; i < 50; i++) {
            guardA.get("user:missing");
        }
        check(dbA2.loads.get() == 1, "缓存空值：首请求打 DB 后缓存 null，后 49 次全部命中空缓存");
        check(guardA.get("user:missing") == null, "读到的是空值而非错误（空值 TTL 必须设短，见主文档 3.3）");

        // ------------------------------------------------------------------
        // 场景 B：缓存击穿 —— 热点 key 过期瞬间，16 个并发请求同时回源
        // ------------------------------------------------------------------
        System.out.println("场景 B：缓存击穿（单个热点 key 过期瞬间并发 miss）");
        int threads = 16;
        // 无防护（对照）：自定义 DataSource 把每次回源「闸」在 DB 门口——
        // 每个线程到达 DB 先报数，主线程确认 16 个都到了再放行，保证竞态是真实发生的而不是臆想
        ManualClock cb = new ManualClock(0);
        AtomicInteger naiveLoads = new AtomicInteger();
        CountDownLatch enteredDb = new CountDownLatch(threads);
        CountDownLatch releaseDb = new CountDownLatch(1);
        CacheAside naiveB = new CacheAside(cb, new DataSource() {
            @Override
            public String load(String key) {
                naiveLoads.incrementAndGet();
                enteredDb.countDown();
                try {
                    releaseDb.await(); // 教学性覆盖：模拟「DB 查询有耗时」，把 16 次 miss 都固定在同一次过期窗口里
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
                return "value:hot";
            }
        }, 60_000, false, false, 0);
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch go = new CountDownLatch(1);
        for (int i = 0; i < threads; i++) {
            pool.submit(() -> {
                try {
                    go.await();
                    naiveB.get("hot:item");
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            });
        }
        go.countDown();
        enteredDb.await(5, TimeUnit.SECONDS);
        releaseDb.countDown();
        pool.shutdown();
        pool.awaitTermination(5, TimeUnit.SECONDS);
        check(naiveLoads.get() == threads, "无防护：热点 key 过期瞬间 " + threads + " 个并发请求全部 miss 回源");

        // 有防护（单飞）：同一波并发请求，只有 1 个线程回源，其余线程等结果
        CountingDataSource dbB2 = new CountingDataSource("hot:item");
        CacheAside guardB = new CacheAside(cb, dbB2, 60_000, false, true, 0);
        runConcurrently(threads, () -> guardB.get("hot:item"));
        check(dbB2.loads.get() == 1, "单飞防护：" + threads + " 个并发请求共享同一次回源，DB 只访问 1 次");
        check(guardB.get("hot:item").equals("value:hot:item"), "所有线程最终都拿到同一份正确数据");

        // ------------------------------------------------------------------
        // 场景 C：缓存雪崩 —— 大批 key 同一时刻集体过期 = 单波回源洪峰
        // ------------------------------------------------------------------
        System.out.println("场景 C：缓存雪崩（大批 key 同时过期 → 单波回源洪峰）");
        int keyCount = 120;
        List<String> keys = java.util.stream.IntStream.range(0, keyCount).mapToObj(i -> "item:" + i).toList();
        ManualClock cc1 = new ManualClock(0);
        CountingDataSource dbC1 = new CountingDataSource(keys.toArray(String[]::new));
        CacheAside noJitter = new CacheAside(cc1, dbC1, 1_000, false, false, 0);
        primeAll(noJitter, keys); // t=0 全部回源一次
        cc1.advance(1_001);       // t=1001：120 个 key 全部在同一时刻过期
        int burstNoJitter = reloadAll(noJitter, keys, dbC1);
        check(burstNoJitter == keyCount, "无抖动：120 个 key 同一毫秒集体过期 → 单波 120 次回源（DB 洪峰）");

        ManualClock cc2 = new ManualClock(0);
        CountingDataSource dbC2 = new CountingDataSource(keys.toArray(String[]::new));
        CacheAside withJitter = new CacheAside(cc2, dbC2, 1_000, false, false, 400);
        primeAll(withJitter, keys); // t=0 全部回源一次
        cc2.advance(1_001);         // 从 t=1001 开始陆续过期（+[0,400)ms 抖动）
        int peakWithJitter = 0;
        for (long step = 0; step <= 450; step += 50) { // 按 50ms 粒度扫过期，统计单步回源峰值
            int before = dbC2.loads.get();
            for (String key : keys) {
                withJitter.get(key); // 已过期的 key 在此刻回源，未过期的不产生 DB 访问
            }
            peakWithJitter = Math.max(peakWithJitter, dbC2.loads.get() - before);
            cc2.advance(50);
        }
        check(peakWithJitter > 0 && peakWithJitter < keyCount,
                "TTL 加 [0,400)ms 抖动：过期时间摊开，任意 50ms 窗口回源峰值 = " + peakWithJitter
                        + " << 无抖动的 " + keyCount + "（DB 不再被单波打满）");
        check(dbC2.loads.get() == keyCount * 2,
                "抖动不减少回源总次数（仍 120×2），只是把同一时刻的洪峰摊平到时间轴上");

        System.out.println();
        System.out.println("全部自检通过。对照主文档 3.3：");
        System.out.println("  - 穿透（数据不存在）：缓存空值（TTL 要短）/ 布隆过滤器（缓存前置过滤）");
        System.out.println("  - 击穿（单个热点过期）：单飞/互斥重建是正解；逻辑过期优化读路径（读旧值+异步重建）");
        System.out.println("  - 雪崩（大批同时过期）：TTL 随机抖动 + 多级缓存（本地缓存仍在） + 限流兜底");
        System.out.println("  - 三兄弟会叠加：穿透 key 一旦变热就是击穿，多个热点同时过期就是雪崩");
    }

    /** 用固定线程池并发执行同一动作并等待全部完成（无外部闸门，任务可自行结束） */
    static void runConcurrently(int threads, Runnable action) throws InterruptedException {
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch start = new CountDownLatch(1);
        CountDownLatch done = new CountDownLatch(threads);
        for (int i = 0; i < threads; i++) {
            pool.submit(() -> {
                try {
                    start.await();
                    action.run();
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
    }

    /** 预热：把全部 key 读一遍（首次全 miss → 回源并写入缓存） */
    static void primeAll(CacheAside cache, List<String> keys) {
        for (String key : keys) {
            cache.get(key);
        }
    }

    /** 把全部 key 读一遍，返回「本趟新增的 DB 回源次数」 */
    static int reloadAll(CacheAside cache, List<String> keys, CountingDataSource db) {
        int before = db.loads.get();
        for (String key : keys) {
            cache.get(key);
        }
        return db.loads.get() - before;
    }
}
