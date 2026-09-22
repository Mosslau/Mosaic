// examples/ex02-caffeine-local-cache/ex02-caffeine-local-cache.java
// Caffeine 本地缓存用法（对应主文档 3.2）：maximumSize / expireAfterWrite / removalListener /
// ticker（虚拟时钟，让过期可被确定地测试）/ recordStats / LoadingCache
// 教学映射：Caffeine = JVM 内缓存（与 Redis 远程缓存互补，见主文档 3.2 的分层表与 ex07）；
//           Guava Cache 是它的前身，Caffeine 用 Window TinyLFU 淘汰算法逼近最优缓存命中率（4 章简注）。
// 设计：注入 ticker 驱动过期（生产不注入，默认系统时钟），演示结果确定可复现。
// 验证环境：OpenJDK 17 + Caffeine 3.1.8（jar 在仓库离线缓存，见 examples/README.md）
// 验证命令（离线缓存已含 caffeine 3.1.8 及编译期依赖）：
//   # 0. 定义 classpath（本机离线 Maven 仓库 /tmp/m2clone 含 caffeine 3.1.8）
//   M2=/tmp/m2clone
//   CP=$M2/com/github/ben-manes/caffeine/caffeine/3.1.8/caffeine-3.1.8.jar:$M2/org/checkerframework/checker-qual/3.37.0/checker-qual-3.37.0.jar:$M2/com/google/errorprone/error_prone_annotations/2.21.1/error_prone_annotations-2.21.1.jar
//   # 1. 编译（在 examples/ex02-caffeine-local-cache/ 目录下执行）
//   javac -cp "$CP" ex02-caffeine-local-cache.java
//   # 2. 运行
//   java -cp "$CP:." CaffeineLocalCacheDemo
//   有 Maven 的环境可在同目录用如下 pom 等价构建（依赖 groupId=com.github.ben-manes:caffeine:3.1.8）：
//   mvn compile exec:java -Dexec.mainClass=CaffeineLocalCacheDemo
// 验证状态：已验证（OpenJDK 17.0.18 + Caffeine 3.1.8 本机实测：javac 编译通过、运行全部 PASS）

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import com.github.benmanes.caffeine.cache.LoadingCache;
import com.github.benmanes.caffeine.cache.RemovalCause;
import com.github.benmanes.caffeine.cache.RemovalListener;
import com.github.benmanes.caffeine.cache.Ticker;

import java.time.Duration;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/** Caffeine 本地缓存演示：容量 / TTL / 淘汰回调 / 统计 / LoadingCache */
final class CaffeineLocalCacheDemo {

    /** 手动时钟：注入 Caffeine 的 ticker，让「时间流逝」可以被测试代码精确控制 */
    static final class ManualTicker implements Ticker {
        private final AtomicLong t = new AtomicLong();

        long nanos() {
            return t.get();
        }

        void advanceNanos(long delta) {
            t.addAndGet(delta);
        }

        @Override
        public long read() {
            return t.get(); // Caffeine 的 ticker 单位是纳秒
        }
    }

    static void check(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError("自检失败: " + label);
        }
        System.out.println("PASS  " + label);
    }

    public static void main(String[] args) {
        System.out.println("场景一：expireAfterWrite —— 写入后 TTL 到期自动失效");
        ManualTicker ticker = new ManualTicker();
        Cache<String, String> ttlCache = Caffeine.newBuilder()
                .ticker(ticker)                       // 用我们的时钟驱动过期（生产不配，默认系统时钟）
                .expireAfterWrite(Duration.ofSeconds(1))
                .recordStats()
                .build();
        ttlCache.put("session:1", "token-abc");
        check(ttlCache.getIfPresent("session:1").equals("token-abc"), "刚写入可命中");
        ticker.advanceNanos(500_000_000);             // 过 500ms
        check(ttlCache.getIfPresent("session:1") != null, "TTL 未到：仍可命中");
        ticker.advanceNanos(600_000_000);             // 累计超过 1s
        ttlCache.cleanUp();
        check(ttlCache.getIfPresent("session:1") == null, "TTL 到点：过期条目自动失效（无需手动删除）");

        System.out.println("场景二：maximumSize —— 容量超限按策略淘汰不常用的条目");
        ManualTicker ticker2 = new ManualTicker();
        Cache<Integer, String> sized = Caffeine.newBuilder()
                .ticker(ticker2)
                .maximumSize(3)
                .recordStats()
                .build();
        sized.put(1, "a");
        sized.put(2, "b");
        sized.put(3, "c");
        sized.put(4, "d");                            // 超过容量 3：触发淘汰
        sized.cleanUp();
        check(sized.estimatedSize() <= 3, "容量封顶：最多保留 3 个条目（第 4 个 put 触发淘汰）");
        check(sized.stats().evictionCount() >= 1, "stats 记录了驱逐数（上线时用驱逐率判断容量是否合理）");
        check(sized.getIfPresent(4).equals("d"), "最新写入的条目保留（Window TinyLFU 倾向保留更常用的）");
        check(sized.getIfPresent(1) == null, "先写入且此后未被访问的 key 先被淘汰（近似 LRU 的最小示例）");

        System.out.println("场景三：LoadingCache —— 自动加载，同一 key 重复读只加载一次");
        ManualTicker ticker3 = new ManualTicker();
        AtomicInteger loads = new AtomicInteger();
        LoadingCache<String, String> loading = Caffeine.newBuilder()
                .ticker(ticker3)
                .expireAfterWrite(Duration.ofSeconds(5))
                .build(key -> {                       // CacheLoader：miss 时自动回源（生产里是查 DB/调下游）
                    loads.incrementAndGet();
                    return "loaded:" + key;
                });
        check(loading.get("product:1").equals("loaded:product:1"), "首次 get 自动加载并缓存");
        check(loading.get("product:1").equals("loaded:product:1"), "第二次 get 命中缓存（值一致）");
        check(loads.get() == 1, "同一 key 只回源 1 次 —— 这就是缓存的全部意义");
        ticker3.advanceNanos(6_000_000_000L);         // 超过 5s TTL
        check(loading.get("product:1") != null, "过期后再次 get 重新加载（旧值被丢弃，读到的仍是新值）");
        check(loads.get() == 2, "重新加载后回源次数 +1 —— 过期重建是常态，所以下面场景四的统计很重要");
        check(loading.get("product:2").equals("loaded:product:2"), "不同 key 独立加载，互不污染");

        System.out.println("场景四：recordStats —— 命中率、加载耗时都是可观测的（上线监控的原料）");
        ManualTicker ticker4 = new ManualTicker();
        Cache<String, String> stat = Caffeine.newBuilder()
                .ticker(ticker4)
                .maximumSize(100)
                .expireAfterWrite(Duration.ofSeconds(10))
                .recordStats()
                .build();
        stat.put("k", "v");
        for (int i = 0; i < 9; i++) {
            stat.getIfPresent("k");
        }
        stat.getIfPresent("missing");                 // 1 次 miss
        double hitRate = stat.stats().hitRate();
        check(hitRate >= 0.9, "命中率 = hits / (hits+misses) = 9/10 = 0.9（stats().hitRate()）");
        check(stat.stats().hitCount() == 9 && stat.stats().missCount() == 1,
                "hit/miss 计数与事实一致 —— Caffeine 的 StatsCounter 是压测与容量规划的输入");

        System.out.println();
        System.out.println("全部自检通过。对照主文档 3.2：");
        System.out.println("  - Caffeine 是 JVM 内缓存：毫秒级延迟、不跨进程 —— 适合热点数据的最热层；");
        System.out.println("    数据分片到多实例时各自独立 → 一致性要靠失效广播（见 ex07 / 主文档 4.2）");
        System.out.println("  - 常用调参：maximumSize / expireAfterWrite / recordStats / removalListener");
        System.out.println("  - 生产注意：TTL 别设太长（数据更新看不到）、容量别设太大（占用堆）、");
        System.out.println("    加 recordStats + 命中率监控，命中率掉下来说明缓存策略失效了");
    }
}
