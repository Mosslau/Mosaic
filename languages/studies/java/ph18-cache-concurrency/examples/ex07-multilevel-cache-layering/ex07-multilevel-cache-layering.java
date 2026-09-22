// examples/ex07-multilevel-cache-layering/ex07-multilevel-cache-layering.java
// 多级缓存分层与失效广播（对应主文档 3.2/4.2）：L1 本地缓存(Caffeine) → L2 远程缓存(Redis) → DB
// 教学映射：真实链路的每一级在这里都有对应物 ——
//   L1 Caffeine     = 每个应用实例进程内的本地缓存（内存读写，不跨实例共享）
//   L2 SimRedis     = Redis（跨实例共享的远程缓存；本文件用内存 Map 模拟其 get/set/ttl/订阅语义）
//   L1 失效广播      = Redis pub/sub / keyspace 通知：一处更新，各实例把自己 L1 里的旧值作废
//   DB              = 数据源（本文件用带计数的假数据库模拟）
// 为什么需要广播：L1 是「每实例一份」，实例 A 更新数据后，实例 B 的 L1 仍是旧值 → 一致性窗口。
//   写路径纪律（Cache-Aside）：先写 DB，再删 L2，最后广播失效；各实例收到广播后 invalidate 本地 L1。
// 教学性覆盖：SimRedis 不是真 Redis（协议/RESP/网络不在本文件），只复刻「共享存储 + 变更通知」语义；
//             L1 与 L2 的 TTL 都走同一手动时钟，断言结果确定可复现。
// 验证环境：OpenJDK 17 + Caffeine 3.1.8（classpath 同 examples/ex02，见 examples/README.md）
// 验证命令：
//   # 0. 定义 classpath（同 ex02）
//   M2=/tmp/m2clone
//   CP=$M2/com/github/ben-manes/caffeine/caffeine/3.1.8/caffeine-3.1.8.jar:$M2/org/checkerframework/checker-qual/3.37.0/checker-qual-3.37.0.jar:$M2/com/google/errorprone/error_prone_annotations/2.21.1/error_prone_annotations-2.21.1.jar
//   # 1. 编译（在 examples/ex07-multilevel-cache-layering/ 目录下执行）
//   javac -cp "$CP" ex07-multilevel-cache-layering.java
//   # 2. 运行
//   java -cp "$CP:." MultilevelCacheLayeringDemo
// 验证状态：已验证（OpenJDK 17.0.18 + Caffeine 3.1.8 本机实测：javac 编译通过、运行全部 PASS）

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Consumer;

/** 多级缓存分层（L1 Caffeine → L2 Redis → DB）与跨实例失效广播演示 */
final class MultilevelCacheLayeringDemo {

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

    /** 假数据库：Map 当表，load 计次（DB 访问次数是判断各级缓存是否生效的指标） */
    static final class AppDb {
        private final Map<String, String> table = new ConcurrentHashMap<>();
        final AtomicInteger loads = new AtomicInteger();

        AppDb(String... keys) {
            for (String k : keys) {
                table.put(k, "data:" + k);
            }
        }

        String load(String key) {
            loads.incrementAndGet();
            return table.get(key); // null = DB 里没有
        }

        void update(String key, String newValue) {
            table.put(key, newValue);
        }
    }

    /**
     * SimRedis = 共享远程缓存（对应 Redis）：
     *   get / set(带 TTL) / delete + 变更订阅 —— 任何 set/delete 后向订阅者广播 key。
     * 记录 (value, expiresAt)，读时懒过期（与 examples/ex03/ex04 同一套虚拟时钟约定）。
     */
    static final class SimRedis {
        record Entry(String value, long expiresAt) {
        }

        private final Clock clock;
        private final Map<String, Entry> data = new ConcurrentHashMap<>();
        private final CopyOnWriteArrayList<Consumer<String>> subscribers = new CopyOnWriteArrayList<>();

        SimRedis(Clock clock) {
            this.clock = clock;
        }

        void subscribe(Consumer<String> onKeyChanged) {
            subscribers.add(onKeyChanged);
        }

        String get(String key) {
            Entry e = data.get(key);
            if (e == null || e.expiresAt <= clock.now()) {
                return null;
            }
            return e.value;
        }

        void set(String key, String value, long ttlMs) {
            data.put(key, new Entry(value, clock.now() + ttlMs));
            broadcast(key); // 写入也广播：别人本地若缓存旧值应立即作废
        }

        void delete(String key) {
            data.remove(key);
            broadcast(key);
        }

        private void broadcast(String key) {
            for (Consumer<String> s : subscribers) {
                s.accept(key);
            }
        }
    }

    /**
     * 一个应用实例：本地 L1(Caffeine) + 共享 L2(SimRedis) + DB。
     * read 顺序 L1 → L2 → DB（Cache-Aside 逐级回填）；订阅 L2 变更广播，收到即清本地 L1。
     */
    static final class CacheNode {
        private final SimRedis remote;
        private final AppDb db;
        private final Cache<String, String> l1;

        CacheNode(SimRedis remote, AppDb db, ManualClock clock) {
            this.remote = remote;
            this.db = db;
            this.l1 = Caffeine.newBuilder()
                    .ticker(() -> clock.now() * 1_000_000L) // Caffeine ticker 单位纳秒；手动时钟驱动 TTL
                    .maximumSize(10_000)
                    .expireAfterWrite(Duration.ofSeconds(30)) // L1 TTL 短：本地层优先「新鲜」
                    .build();
            remote.subscribe(key -> l1.invalidate(key));     // 收到失效广播：作废本地旧值
        }

        /** 读：L1 命中即返 → L2 miss 查 L2 → L2 miss 才回源 DB，逐级回填 */
        String read(String key) {
            String v = l1.getIfPresent(key);
            if (v != null) {
                return v;                                     // L1 命中（进程内存，最快）
            }
            v = remote.get(key);
            if (v != null) {
                l1.put(key, v);                               // L2 命中 → 回填 L1
                return v;
            }
            v = db.load(key);                                 // 两级都 miss → 回源 DB
            if (v != null) {
                remote.set(key, v, 120_000);                  // 回填 L2（TTL 120s，比 L1 长）
                l1.put(key, v);                               // 回填 L1
            }
            return v;
        }

        /** 更新（写路径纪律）：写 DB → 删 L2（不改成新值）→ 广播让全部实例清本地 L1 */
        void update(String key, String newValue) {
            db.update(key, newValue);
            remote.delete(key); // 删比改干净：避免「改一半的中间值」被读到（Cache-Aside 结论，见 4.2）
        }

        long l1Size() {
            l1.cleanUp();
            return l1.estimatedSize();
        }
    }

    static void check(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError("自检失败: " + label);
        }
        System.out.println("PASS  " + label);
    }

    public static void main(String[] args) {
        ManualClock clock = new ManualClock(0);
        AppDb db = new AppDb("product:1", "product:2");
        SimRedis redis = new SimRedis(clock);
        CacheNode nodeA = new CacheNode(redis, db, clock);
        CacheNode nodeB = new CacheNode(redis, db, clock);

        System.out.println("场景一：分层读 —— 请求按 L1 → L2 → DB 逐级走，只有首读打到数据库");
        check(nodeA.read("product:1").equals("data:product:1"), "nodeA 首读：L1/L2 都 miss → 回源 DB，逐级回填");
        check(db.loads.get() == 1, "nodeA 首读打 DB 1 次");
        check(nodeB.read("product:1").equals("data:product:1"), "nodeB 首读：L1 miss、L2 命中（nodeA 已回填）→ 只回填 L1");
        check(db.loads.get() == 1, "nodeB 首读零 DB 访问 —— L2 跨实例共享，这是本地缓存做不到的");
        for (int i = 0; i < 5; i++) {
            nodeA.read("product:1");
        }
        check(db.loads.get() == 1, "后续 5 次全部命中 L1 —— 三级链路把绝大多数压力挡在缓存里");

        System.out.println("场景二：更新 + 失效广播 —— 一处更新，所有实例的 L1 同时作废");
        check(nodeA.l1Size() == 1 && nodeB.l1Size() == 1, "更新前：A、B 两个实例的 L1 都缓存了 product:1");
        nodeA.update("product:1", "data:product:1-v2"); // 写 DB → 删 L2 → 广播
        check(nodeA.l1Size() == 0 && nodeB.l1Size() == 0,
                "广播送达：A 和 B 的本地 L1 都被清空 —— 不广播的话 B 会一直读到旧值");
        check(redis.get("product:1") == null, "L2 已被删除（不是改成 v2：删除让读方必须回源拿到新值）");
        check(nodeB.read("product:1").equals("data:product:1-v2"), "nodeB 重读：L2 已删 → 回源 DB 拿新值并逐级回填");
        check(db.loads.get() == 2, "一致性窗口之后读到的都是新值（DB 访问计数 1 → 2）");

        System.out.println("场景三：两级 TTL 分工 —— L1 短保新鲜、L2 长兜底");
        ManualClock clock3 = new ManualClock(0);
        AppDb db3 = new AppDb("product:1");
        SimRedis redis3 = new SimRedis(clock3);
        CacheNode nodeC = new CacheNode(redis3, db3, clock3);
        nodeC.read("product:1"); // t=0 回源：L1、L2 都回填
        check(db3.loads.get() == 1, "首读回源 DB 一次");
        clock3.advance(31_000); // 超过 L1 的 30s TTL，未到 L2 的 120s TTL
        check(nodeC.l1Size() == 0, "L1 TTL 到点自动过期（本地层保持新鲜）");
        check(nodeC.read("product:1").equals("data:product:1"), "重读：L1 miss 但 L2 命中 → 不碰 DB");
        check(db3.loads.get() == 1, "L2 兜住了这次读取，DB 零访问");
        clock3.advance(90_000); // 累计 121s：超过 L2 的 120s TTL
        nodeC.read("product:1");
        check(db3.loads.get() == 2, "L2 也过期后回到 DB —— TTL 是缓存层的「最终兜底」，让旧数据终究会被淘汰");

        System.out.println();
        System.out.println("全部自检通过。对照主文档 3.2/4.2：");
        System.out.println("  - L1(Caffeine) 读最快但不共享、一致性靠广播；L2(Redis) 共享但每次多一次网络 RTT");
        System.out.println("  - 写路径纪律：先写 DB，再删缓存，最后广播失效 —— 顺序错了会放大不一致窗口");
        System.out.println("  - 广播是最终一致的最后一环：真 Redis 用 pub/sub / keyspace 通知；丢广播靠 TTL 兜底");
        System.out.println("  - 本文件是单进程模拟；多实例真跑时 L1 是每 JVM 一份，语义与场景二一致（见主文档 4.2）");
    }
}
