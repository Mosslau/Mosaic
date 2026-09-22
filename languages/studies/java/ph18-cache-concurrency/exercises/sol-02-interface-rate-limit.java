// exercises/sol-02-interface-rate-limit.java —— 练习 2 参考实现：接口限流（roadmap ph18 练习：接口限流）
// 目标还原（见 exercises/README.md）：按调用方（用户/接口维度）做键控限流 + 总量限流 + 空闲回收。
//   生产对应：接口限流的落地形态 —— 网关/Sentinel（ph16 讲的是治理框架接入）、本练习讲算法与键控本身：
//   单机版可用本文件语义（ConcurrentHashMap + 每键限流器），多实例要搬进 Redis（主文档 3.5 的 Redis+Lua）。
// 实现要点：
//   - 键控限流：每个业务键（用户 id/接口名）独立配额，互不影响 —— 单一用户刷爆不能拖垮全体。
//   - 总量限流：全局限流器再兜一层（不限总量的话，攻击者换 key 就能绕过键控）。
//   - 空闲回收：长期不活跃的键删掉，防止「每个用户一个限流器对象」的内存无限增长。
//   - 底层用「令牌桶（容量限突发）」，语义与 examples/ex05 一致；并发正确性由 synchronized 保证。
// 教学性覆盖：限流器对象的内存回收用简单的“最近活跃时间 + 惰性清理”；生产一般直接交给本地缓存
//             （Caffeine 容量封顶即淘汰）或 Redis key 的 TTL，本参考实现把机制显式写出来便于理解。
// 验证环境：OpenJDK 17（javac -version -> 17.x）；无第三方依赖
// 验证命令：
//   # 1. 编译（在 exercises/ 目录下执行）
//   javac sol-02-interface-rate-limit.java
//   # 2. 运行
//   java InterfaceRateLimitDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：javac 编译通过、运行全部 PASS）

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/** 接口限流练习参考实现：键控限流（令牌桶）× 总量限流 × 空闲回收 */
final class InterfaceRateLimitDemo {

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

    /** 单键限流器：令牌桶（满桶可突发、恒定速率补充；ratePerSecond<=0 时不再补充，便于断言） */
    static final class TokenBucket {
        private final Clock clock;
        private final int capacity;
        private final double tokensPerMs;
        private double tokens;
        private long lastRefill;

        TokenBucket(Clock clock, int capacity, double ratePerSecond) {
            this.clock = clock;
            this.capacity = capacity;
            this.tokensPerMs = ratePerSecond / 1000.0;
            this.tokens = capacity;
            this.lastRefill = clock.now();
        }

        synchronized boolean tryAcquire() {
            long now = clock.now();
            tokens = Math.min(capacity, tokens + (now - lastRefill) * tokensPerMs);
            lastRefill = now;
            if (tokens < 1.0) {
                return false;
            }
            tokens -= 1.0;
            return true;
        }
    }

    /**
     * 键控限流器：
     *   - perKey：每个键一个独立令牌桶（容量、速率相同但互不影响）
     *   - 全局总量：global 桶再限一次（防止换 key 绕过）
     *   - 空闲回收：超过 idleMs 未访问的键被惰性清除（内存有界）
     */
    static final class KeyedRateLimiter {
        private record Bucket(String key, TokenBucket bucket, long lastActiveAt) {
        }

        private final Clock clock;
        private final int perKeyCapacity;
        private final double perKeyRatePerSecond;
        private final long idleMs;
        private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();
        private final TokenBucket global;

        KeyedRateLimiter(Clock clock, int perKeyCapacity, double perKeyRatePerSecond,
                         int globalCapacity, double globalRatePerSecond, long idleMs) {
            this.clock = clock;
            this.perKeyCapacity = perKeyCapacity;
            this.perKeyRatePerSecond = perKeyRatePerSecond;
            this.idleMs = idleMs;
            this.global = new TokenBucket(clock, globalCapacity, globalRatePerSecond);
        }

        /** 调用方维度放行判断：先过全局总量，再过本键配额 */
        boolean tryAcquire(String key) {
            if (!global.tryAcquire()) {
                return false; // 总量到顶：不管哪个 key 都拒绝（换 key 也绕不过这一层）
            }
            return keyBucket(key).tryAcquire();
        }

        private TokenBucket keyBucket(String key) {
            long now = clock.now();
            // 惰性清理 + 更新活跃时间：compute 保证「检查 + 重建」原子
            return buckets.compute(key, (k, old) -> {
                if (old == null || now - old.lastActiveAt() >= idleMs) {
                    return new Bucket(k, new TokenBucket(clock, perKeyCapacity, perKeyRatePerSecond), now);
                }
                return new Bucket(k, old.bucket(), now); // 沿用老桶（配额连续），只刷新活跃时间
            }).bucket();
        }

        int activeKeys() {
            return buckets.size();
        }

        /** 显式清理：把空闲超过 idleMs 的键全部移除（也可交给上面的惰性路径自动做） */
        void pruneIdle() {
            long now = clock.now();
            buckets.entrySet().removeIf(e -> now - e.getValue().lastActiveAt() >= idleMs);
        }
    }

    static void check(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError("自检失败: " + label);
        }
        System.out.println("PASS  " + label);
    }

    public static void main(String[] args) throws InterruptedException {
        System.out.println("场景一：键控隔离 —— 单个用户刷爆自己的配额，不影响其他用户");
        ManualClock clock = new ManualClock(0);
        KeyedRateLimiter limiter = new KeyedRateLimiter(clock, 5, 0,
                100_000, 0, 60_000); // per-key 容量 5、不补充；global 容量极大不设限
        int acceptedA = 0;
        for (int i = 0; i < 10; i++) {
            if (limiter.tryAcquire("user-A")) {
                acceptedA++;
            }
        }
        check(acceptedA == 5, "user-A 连发 10 次 → 只放行 5 次（容量=5，令牌耗尽即拒绝）");
        int acceptedB = 0;
        for (int i = 0; i < 5; i++) {
            if (limiter.tryAcquire("user-B")) {
                acceptedB++;
            }
        }
        check(acceptedB == 5, "user-B 仍有自己的 5 次配额 → 键控隔离：A 刷爆不影响 B");

        System.out.println("场景二：总量限流 —— 攻击者换 key 也绕不过全局配额");
        ManualClock clock2 = new ManualClock(0);
        KeyedRateLimiter guarded = new KeyedRateLimiter(clock2, 1_000, 0,
                20, 0, 60_000); // per-key 容量极大，全局总量只有 20
        int totalAccepted = 0;
        for (int i = 0; i < 30; i++) {
            if (guarded.tryAcquire("attacker-" + i)) { // 每次换一个新 key
                totalAccepted++;
            }
        }
        check(totalAccepted == 20, "换了 30 个 key 也只放行 20 次（全局总量兜底 —— 只做键控会被换 key 绕过）");

        System.out.println("场景三：并发正确性 —— 200 线程抢同一用户配额，放行数恰好等于容量（不超放）");
        ManualClock clock3 = new ManualClock(0);
        KeyedRateLimiter concurrent = new KeyedRateLimiter(clock3, 8, 0,
                100_000, 0, 60_000);
        ExecutorService pool = Executors.newFixedThreadPool(32);
        CountDownLatch start = new CountDownLatch(1);
        CountDownLatch done = new CountDownLatch(200);
        AtomicInteger ok = new AtomicInteger();
        for (int i = 0; i < 200; i++) {
            pool.submit(() -> {
                try {
                    start.await();
                    if (concurrent.tryAcquire("rush")) {
                        ok.incrementAndGet();
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
        check(ok.get() == 8, "200 并发抢 8 个配额 → 恰好放行 8（0 超放、0 漏放）");

        System.out.println("场景四：空闲回收 —— 长期不活跃的键不占内存");
        ManualClock clock4 = new ManualClock(0);
        KeyedRateLimiter recycler = new KeyedRateLimiter(clock4, 3, 0,
                100_000, 0, 60_000);
        recycler.tryAcquire("user-old");
        recycler.tryAcquire("user-new");
        check(recycler.activeKeys() == 2, "两个活跃键都在表中");
        clock4.advance(61_000); // 两个键都超过 idleMs=60s
        recycler.pruneIdle();
        check(recycler.activeKeys() == 0, "显式清理后空闲键全部回收（内存有界，不会随 key 无限增长）");
        recycler.tryAcquire("user-old"); // 再次访问：重新建桶（配额重新给满 —— 可接受的折中）
        check(recycler.activeKeys() == 1, "冷 key 回归自动重建配额（无需手工登记）");

        System.out.println();
        System.out.println("全部自检通过。对照主文档 3.5 与 exercises/README：");
        System.out.println("  - 键控限流管「单用户/单接口的配额」，总量限流管「整体水位」，缺总量 = 可被换 key 绕过");
        System.out.println("  - 令牌桶容量决定突发上限、速率决定长期均值（见 examples/ex05 的完整对比）");
        System.out.println("  - 多实例部署时把桶搬进 Redis：Lua 脚本原子地『取令牌/更新计数』，见主文档 3.5");
    }
}
