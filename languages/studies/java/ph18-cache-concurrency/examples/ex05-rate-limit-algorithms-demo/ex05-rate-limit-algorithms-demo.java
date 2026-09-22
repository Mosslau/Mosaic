// examples/ex05-rate-limit-algorithms-demo/ex05-rate-limit-algorithms-demo.java
// 五种限流形态 + 统一自检（对应主文档 3.5/4.3）：固定窗口、滑动窗口日志、滑动窗口计数器、令牌桶、漏桶
// 教学映射：固定窗口「窗口边界可瞬时放行 2×capacity」、滑动窗口日志「精确但每个请求记一个时间戳」、
//           滑动窗口计数器「只记两个窗口的计数、按滑出比例加权，折中」、令牌桶「容量限突发 + 恒定速率补充」、
//           漏桶「出桶速率恒定，把一切抖动在上游摊平」。生产形态见主文档 3.5：Guava RateLimiter ≈ 令牌桶（可预支），
//           Sentinel 匀速排队 ≈ 漏桶，Redis + Lua 脚本 = 分布式版（计数/令牌搬进 Redis）。
// 设计：时间全部走注入的 Clock；每个场景用独立「手动时钟」，不 sleep、不依赖真实时间 —— 断言确定可复现。
// 教学性覆盖：为聚焦算法本身，省略了优雅停止、指标上报与配置化（工程细节见 ph12 测试/ph19 运维）。
// 验证环境：OpenJDK 17（javac -version -> 17.x）；无第三方依赖
// 验证命令：
//   # 1. 编译（在 examples/ex05-rate-limit-algorithms-demo/ 目录下执行）
//   javac ex05-rate-limit-algorithms-demo.java
//   # 2. 运行（文件名与类名不一致：单一文件 + 非 public 类，参照 ph17 examples 约定）
//   java RateLimitAlgorithmsDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：javac 编译通过、运行全部 PASS）

import java.util.ArrayDeque;
import java.util.Deque;

/** 五种限流算法统一演示 */
final class RateLimitAlgorithmsDemo {

    /** 时间源：生产注入 System::currentTimeMillis，演示注入手动时钟 */
    interface Clock {
        long now();
    }

    /** 手动时钟 */
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

    /** 统一限流器抽象 */
    interface Limiter {
        /** 放行一次返回 true；false = 拒绝 */
        boolean tryAcquire();
    }

    // ------------------------------------------------------------------
    // 1. 固定窗口计数器：每 windowMs 一个窗口，窗口内最多 capacity 次
    // ------------------------------------------------------------------
    static final class FixedWindowLimiter implements Limiter {
        private final Clock clock;
        private final long windowMs;
        private final int capacity;
        private long windowStart;
        private int count;

        FixedWindowLimiter(Clock clock, long windowMs, int capacity) {
            this.clock = clock;
            this.windowMs = windowMs;
            this.capacity = capacity;
            this.windowStart = clock.now();
        }

        @Override
        public synchronized boolean tryAcquire() {
            long now = clock.now();
            if (now - windowStart >= windowMs) { // 窗口整段到期：整体翻篇
                windowStart = now;
                count = 0;
            }
            if (count >= capacity) {
                return false;
            }
            count++;
            return true;
        }
    }

    // ------------------------------------------------------------------
    // 2. 滑动窗口日志：窗口随当前时刻滑动，记录每个请求的时间戳
    // ------------------------------------------------------------------
    static final class SlidingWindowLogLimiter implements Limiter {
        private final Clock clock;
        private final long windowMs;
        private final int capacity;
        private final Deque<Long> hits = new ArrayDeque<>();

        SlidingWindowLogLimiter(Clock clock, long windowMs, int capacity) {
            this.clock = clock;
            this.windowMs = windowMs;
            this.capacity = capacity;
        }

        @Override
        public synchronized boolean tryAcquire() {
            long now = clock.now();
            // 只保留 (now - windowMs, now] 内的请求：窗口是连续滑动的，边界处没有翻篇
            while (!hits.isEmpty() && hits.peekFirst() <= now - windowMs) {
                hits.pollFirst();
            }
            if (hits.size() >= capacity) {
                return false;
            }
            hits.addLast(now);
            return true;
        }
    }

    // ------------------------------------------------------------------
    // 3. 滑动窗口计数器：只记上一/当前两个对齐窗口的计数，按滑出比例给上一窗口加权
    // ------------------------------------------------------------------
    static final class SlidingWindowCounterLimiter implements Limiter {
        private final Clock clock;
        private final long windowMs;
        private final int capacity;
        private long prevWindowStart;
        private int prevCount; // 上一个完整对齐窗口内的计数
        private int currCount; // 当前对齐窗口内的计数

        SlidingWindowCounterLimiter(Clock clock, long windowMs, int capacity) {
            this.clock = clock;
            this.windowMs = windowMs;
            this.capacity = capacity;
            this.prevWindowStart = clock.now() / windowMs * windowMs - windowMs;
        }

        @Override
        public synchronized boolean tryAcquire() {
            long now = clock.now();
            long currStart = now / windowMs * windowMs; // 当前所在的对齐窗口起点
            if (currStart > prevWindowStart + windowMs) {
                // 跨过至少两个窗口：上一窗口与当前窗口之间的计数早已全部滑出，清零重来
                prevCount = 0;
                currCount = 0;
                prevWindowStart = currStart;
            } else if (currStart > prevWindowStart) {
                // 恰好进入一个新窗口：当前窗口变成「上一窗口」
                prevCount = currCount;
                currCount = 0;
                prevWindowStart = currStart;
            }
            // 上一窗口的请求已滑出 (now - currStart)/windowMs 的比例，剩下的部分仍占额度
            double remainingRatio = 1.0 - (now - currStart) / (double) windowMs;
            double estimate = prevCount * remainingRatio + currCount;
            if (estimate >= capacity) {
                return false;
            }
            currCount++;
            return true;
        }
    }

    // ------------------------------------------------------------------
    // 4. 令牌桶：容量限突发，tokensPerSecond 恒定补充
    // ------------------------------------------------------------------
    static final class TokenBucketLimiter implements Limiter {
        private final Clock clock;
        private final int capacity;
        private final double tokensPerMs;
        private double tokens;
        private long lastRefill;

        TokenBucketLimiter(Clock clock, int capacity, double tokensPerSecond) {
            this.clock = clock;
            this.capacity = capacity;
            this.tokensPerMs = tokensPerSecond / 1000.0;
            this.tokens = capacity; // 初始满桶：允许到点瞬间的整桶突发
            this.lastRefill = clock.now();
        }

        @Override
        public synchronized boolean tryAcquire() {
            long now = clock.now();
            tokens = Math.min(capacity, tokens + (now - lastRefill) * tokensPerMs); // 先按间隔补令牌
            lastRefill = now;
            if (tokens < 1.0) {
                return false;
            }
            tokens -= 1.0;
            return true;
        }
    }

    // ------------------------------------------------------------------
    // 5. 漏桶：有界队列 + 单服务台（每 drainMs 出一个）；出桶速率恒定
    //    建模：每个被接受的消息分配一个「离桶时刻」，相邻离桶时刻至少间隔 drainMs
    // ------------------------------------------------------------------
    static final class LeakyBucketLimiter implements Limiter {
        private final Clock clock;
        private final int queueCapacity;
        private final long drainMs;
        private final Deque<Long> departures = new ArrayDeque<>(); // 已接受消息的离桶时刻（升序）
        private long lastDeparture = Long.MIN_VALUE / 2;

        LeakyBucketLimiter(Clock clock, int queueCapacity, long drainMs) {
            this.clock = clock;
            this.queueCapacity = queueCapacity;
            this.drainMs = drainMs;
        }

        @Override
        public synchronized boolean tryAcquire() {
            long now = clock.now();
            while (!departures.isEmpty() && departures.peekFirst() <= now) {
                departures.pollFirst(); // 已离桶的消息腾出队列位置
            }
            if (departures.size() >= queueCapacity) {
                return false; // 桶满：溢出即丢（削峰靠丢弃而非无限排队）
            }
            long departure = Math.max(now, lastDeparture) + drainMs; // 与前一个离桶时刻至少隔 drainMs
            lastDeparture = departure;
            departures.addLast(departure);
            return true;
        }
    }

    static void check(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError("自检失败: " + label);
        }
        System.out.println("PASS  " + label);
    }

    /** 连续尝试 n 次，返回放行次数 */
    static int accept(Limiter limiter, int n) {
        int ok = 0;
        for (int i = 0; i < n; i++) {
            if (limiter.tryAcquire()) {
                ok++;
            }
        }
        return ok;
    }

    public static void main(String[] args) {
        System.out.println("场景一：固定窗口的边界突发 —— 窗口临界两侧可在瞬时放行 2×capacity");
        ManualClock c1 = new ManualClock(0);
        FixedWindowLimiter fw = new FixedWindowLimiter(c1, 1_000, 3);
        check(accept(fw, 10) == 3, "固定窗口：窗口内放行 3 次，第 4 次起被拒");
        c1.advance(999);
        check(fw.tryAcquire() == false, "t=999 仍属原窗口，不放行");
        c1.advance(1); // t=1000：整窗到期，整体翻篇
        check(accept(fw, 3) == 3, "t=1000 新窗口立刻又能放行 3 次");
        check(fw.tryAcquire() == false,
                "陷阱：t=0 放行的 3 次 + t=1000 放行的 3 次 = 1ms 内 6 次 >> capacity=3 —— 边界突发（滑动窗口要解决的）");

        System.out.println("场景二：滑动窗口日志 —— 谁滑出谁释放名额，不整体翻篇");
        ManualClock c2 = new ManualClock(0);
        SlidingWindowLogLimiter sw = new SlidingWindowLogLimiter(c2, 1_000, 3);
        check(sw.tryAcquire() == true, "t=0 放行 1 次（记时间戳 0）");
        c2.advance(100);
        check(sw.tryAcquire() == true, "t=100 放行 1 次");
        c2.advance(100);
        check(sw.tryAcquire() == true, "t=200 放行 1 次（窗口内共 3 次，容量已满）");
        c2.advance(699); // t=899
        check(sw.tryAcquire() == false, "t=899：三个请求都还在 (now-1000, now] 内，被拒");
        c2.advance(101); // t=1000：只有 t=0 那个滑出窗口（<= 1000-1000）
        check(sw.tryAcquire() == true, "t=1000：仅滑出的 1 个释放名额 → 放行 1 次");
        check(sw.tryAcquire() == false,
                "t=100/200 的请求仍在窗口内 → 继续拒绝（对比固定窗口此处会整窗清零放行 3 次）");

        System.out.println("场景三：滑动窗口计数器 —— 只记两窗计数，边界后仍按比例占用额度");
        ManualClock c3 = new ManualClock(0);
        SlidingWindowCounterLimiter sc = new SlidingWindowCounterLimiter(c3, 1_000, 3);
        check(accept(sc, 4) == 3, "第一个对齐窗口内放行 3 次，第 4 次被拒");
        c3.advance(1_001); // 进入新对齐窗口（1000 起）
        check(accept(sc, 2) == 1,
                "t=1001 虽是「新窗口」，但上一窗口 3 次仍有约 0.999 权重未滑出 → 估算 2.997 只放行 1 次"
                        + "（固定窗口在此刻会整窗清零放行 3 次）");
        c3.advance(499); // t=1500：上一窗口已滑出约一半
        check(accept(sc, 2) == 1, "权重降到 0.5：估算 = 3×0.5 + 1 = 2.5 → 再放行 1 次");
        check(sc.tryAcquire() == false, "接着估算 = 1.5 + 2 = 3.5 >= 3 → 拒绝（额度随上一窗口滑出而渐进释放）");

        System.out.println("场景四：令牌桶 —— 容量限突发、恒定速率补充");
        ManualClock c4 = new ManualClock(0);
        TokenBucketLimiter tb = new TokenBucketLimiter(c4, 5, 10); // 容量 5，每秒补 10 个
        check(accept(tb, 8) == 5, "初始满桶：瞬时最多突发 5 个");
        c4.advance(100);
        check(accept(tb, 2) == 1, "100ms 只补 1 个令牌 → 放行 1 次");
        c4.advance(500); // 累计 t=600：应补 6 个但桶满封顶 5
        check(accept(tb, 10) == 5, "补充受容量封顶，最多再突发 5 个");
        check(tb.tryAcquire() == false, "令牌耗尽后按速率缓缓补充（速率恒 10/s）");
        c4.advance(1_000);
        check(accept(tb, 11) == 5, "等 1 秒补 10 个，但桶满仍是 5 → 桶容量就是突发上限");

        System.out.println("场景五：漏桶 —— 出桶速率恒定，把突发摊平成匀速");
        ManualClock c5 = new ManualClock(0);
        LeakyBucketLimiter lb = new LeakyBucketLimiter(c5, 3, 1_000); // 队列容量 3，每秒出 1 个
        check(accept(lb, 5) == 3, "瞬时最多入桶 3 个，桶满即溢出（漏桶不允许超出服务速率的突发）");
        c5.advance(1_000);
        check(lb.tryAcquire() == true, "1 秒后第 1 个消息离桶，腾出 1 个位置");
        check(accept(lb, 3) == 0, "刚补的位置又被占满，继续拒绝（出桶节奏恒定 1 个/秒）");
        c5.advance(999);
        check(lb.tryAcquire() == false, "还没到下一个离桶时刻，仍拒绝");
        c5.advance(1);
        check(lb.tryAcquire() == true, "又过了 1 秒第 2 个离桶 → 精确按 drainMs 匀速放行");

        System.out.println();
        System.out.println("全部自检通过。对照主文档 3.5/4.3：");
        System.out.println("  - 固定窗口最省内存但有边界突发；滑动窗口日志最精确但 O(窗口内请求数) 内存；");
        System.out.println("    滑动窗口计数器只记两窗计数按比例加权，是内存与精度的折中（Sentinel 默认）");
        System.out.println("  - 令牌桶：允许突发 + 平滑速率（业界最常用，Guava RateLimiter 系）；");
        System.out.println("    漏桶：绝对匀速，把抖动全部摊平到上游（对下游最友好）");
        System.out.println("  - 单机 synchronized 就够；多实例要搬进 Redis 让计数全局一致（主文档 3.5 的 Redis + Lua）");
    }
}
