// examples/ex04-distributed-lock-semantics-demo/ex04-distributed-lock-semantics-demo.java
// 分布式锁语义模拟（对应主文档 3.4/4.4）：SETNX + TTL 持有、唯一标识 value、Lua 原子释放、看门狗续期
// 教学映射：本文件的 LockStorage 接口逐条对应 Redis 原语 ——
//   setIfAbsent        ≈ SET key value NX EX ttl（拿锁 + 原子设过期）
//   get                ≈ GET key
//   compareAndDelete   ≈ Lua 脚本：if redis.call('get', key) == value then return redis.call('del', key) end
//   expireIfOwner      ≈ Lua 脚本看门狗续期：持有者才能续
// 三个经典坑逐一出演（面试与生产都高频）：
//   ① 拿锁不设超时：持锁方崩溃 → 锁永不释放（死锁）
//   ② 释放不校验 value：A 锁超时被 B 顶上后，A 的 finally 把 B 的锁删了（两把锁并存，临界区并发）
//   ③ 业务比锁长：任务没跑完锁先到期 → 需要「看门狗」续期（Redisson 默认行为），或给任务设超时兜底
// 设计：锁存储的过期判断走注入时钟，演示用虚拟时钟拨时间；多线程语义用同一 JVM 内存存储模拟
//       （真正的分布式性在「多 JVM 共享同一个存储」，见主文档 4.4 —— 本文件聚焦拿/放/校验协议本身）。
// 验证环境：OpenJDK 17（javac -version -> 17.x）；无第三方依赖
// 验证命令：
//   # 1. 编译（在 examples/ex04-distributed-lock-semantics-demo/ 目录下执行）
//   javac ex04-distributed-lock-semantics-demo.java
//   # 2. 运行
//   java DistributedLockSemanticsDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：javac 编译通过、运行全部 PASS）

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/** 分布式锁语义演示：三种错误形态 + 一种正确形态 */
final class DistributedLockSemanticsDemo {

    /** 时间源（演示用虚拟时钟） */
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

    /**
     * 锁存储抽象 = Redis 的 key 操作子集。
     * 教学性覆盖：内存 ConcurrentHashMap 实现各方法的原子性并模拟过期；真实 Redis 用 SETNX/Lua，
     * 协议命令见每个方法注释 —— 语义完全同构，只是实现载体不同。
     */
    interface LockStorage {

        /** SET key value NX EX ttlMs：key 不存在才写入并设过期，返回是否拿到锁 */
        boolean setIfAbsent(String key, String value, long ttlMs);

        /** GET key */
        String get(String key);

        /** Lua：if GET(key) == value then DEL(key) end —— 只有持有者本人能释放 */
        boolean compareAndDelete(String key, String value);

        /** DEL key —— 裸删（不带 value 校验，是「误删别人锁」事故的元凶，见场景二） */
        boolean delete(String key);

        /** Lua 看门狗：if GET(key) == value then EXPIRE(key, ttlMs) end —— 只有持有者能续期 */
        boolean expireIfOwner(String key, String value, long ttlMs);

        /** 当前是否有人持有（供断言） */
        boolean isHeld(String key);
    }

    /** 内存实现：懒过期（读时判断 ttl 是否已过），把 Redis 服务端过期语义模拟出来 */
    static final class InMemoryLockStorage implements LockStorage {
        private final Clock clock;
        private final Map<String, Entry> data = new ConcurrentHashMap<>();

        record Entry(String value, long expiresAt) {
        }

        InMemoryLockStorage(Clock clock) {
            this.clock = clock;
        }

        @Override
        public synchronized boolean setIfAbsent(String key, String value, long ttlMs) {
            Entry cur = data.get(key);
            long now = clock.now();
            if (cur != null && cur.expiresAt > now) {
                return false; // 未过期的旧锁在，拿不到
            }
            data.put(key, new Entry(value, ttlMs <= 0 ? Long.MAX_VALUE : now + ttlMs));
            return true;
        }

        @Override
        public synchronized String get(String key) {
            Entry cur = data.get(key);
            if (cur == null || cur.expiresAt <= clock.now()) {
                return null; // 已过期视为不存在（Redis 是服务端惰性删除 + 定期删除）
            }
            return cur.value;
        }

        @Override
        public synchronized boolean compareAndDelete(String key, String value) {
            Entry cur = data.get(key);
            long now = clock.now();
            if (cur == null || cur.expiresAt <= now) {
                return false;
            }
            if (!cur.value.equals(value)) {
                return false; // value 不匹配：锁已是别人的，绝不能删
            }
            data.remove(key);
            return true;
        }

        @Override
        public synchronized boolean delete(String key) {
            return data.remove(key) != null;
        }

        @Override
        public synchronized boolean expireIfOwner(String key, String value, long ttlMs) {
            Entry cur = data.get(key);
            if (cur == null || !cur.value.equals(value)) {
                return false;
            }
            data.put(key, new Entry(value, clock.now() + ttlMs));
            return true;
        }

        @Override
        public synchronized boolean isHeld(String key) {
            return get(key) != null;
        }
    }

    /** 正确姿势的锁封装：拿锁（NX+EX）→ 持 token → 释放走 compareAndDelete */
    static final class SafeLock {
        private final LockStorage storage;
        private final Clock clock;
        private final String key;
        private final long ttlMs;
        private String token; // 唯一标识：UUID，释放时校验本人持有

        SafeLock(LockStorage storage, Clock clock, String key, long ttlMs) {
            this.storage = storage;
            this.clock = clock;
            this.key = key;
            this.ttlMs = ttlMs;
        }

        /** 非阻塞尝试拿锁：拿到返回 true 并记下 token */
        boolean tryLock() {
            if (storage.setIfAbsent(key, UUID.randomUUID().toString(), ttlMs)) {
                token = storage.get(key);
                return true;
            }
            return false;
        }

        String token() {
            return token;
        }

        /** 释放：带 token 的原子释放（不是裸 DEL） */
        boolean unlock() {
            return storage.compareAndDelete(key, token);
        }
    }

    static void check(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError("自检失败: " + label);
        }
        System.out.println("PASS  " + label);
    }

    public static void main(String[] args) {
        System.out.println("场景一：错误 ① 拿锁不设超时 —— 持锁方崩溃后锁永不释放（分布式死锁）");
        ManualClock c1 = new ManualClock(0);
        InMemoryLockStorage s1 = new InMemoryLockStorage(c1);
        SafeLock crash = new SafeLock(s1, c1, "order:1001:lock", Long.MAX_VALUE); // ttl 无穷 = 没设超时
        check(crash.tryLock(), "A 拿到锁");
        // A 在处理订单时 JVM 直接宕机：unlock 永远不执行，也没有 TTL 兜底
        c1.advance(3_600_000);
        check(s1.isHeld("order:1001:lock"), "1 小时后锁仍被占（没有 TTL，Redis 不会帮你释放）");
        check(new SafeLock(s1, c1, "order:1001:lock", Long.MAX_VALUE).tryLock() == false,
                "其他线程永远拿不到这把锁 —— 解决方案：拿锁必须 SET NX EX ttl（给锁一个生命周期）");

        System.out.println("场景二：有了 TTL 但没有唯一标识 —— A 超时释放 B 的锁（两把锁并存）");
        ManualClock c2 = new ManualClock(0);
        InMemoryLockStorage s2 = new InMemoryLockStorage(c2);
        SafeLock a = new SafeLock(s2, c2, "stock:sku1:lock", 1_000);
        check(a.tryLock(), "A 拿到锁（持有 1000ms）");
        c2.advance(1_001); // A 的业务没跑完，锁先到期了
        check(s2.isHeld("stock:sku1:lock") == false, "锁已到期自动释放");
        SafeLock b = new SafeLock(s2, c2, "stock:sku1:lock", 1_000);
        check(b.tryLock(), "B 在 A 还没结束时顶上，拿到同一把锁");
        // 错误代码现场：A 的 finally 里写了 storage.delete(key)（裸 DEL，Redis 命令就是 DEL，不带 value 校验）
        boolean naiveDel = s2.delete("stock:sku1:lock");
        check(naiveDel, "A 裸 DEL 把 B 的锁删掉了（事故代码：unlock 里只调 DEL key）");
        check(s2.isHeld("stock:sku1:lock") == false,
                "B 以为还持锁、A 也以为释放完 —— 实际锁已空，C 能进来 → A/B 两个临界区并发执行");

        System.out.println("场景三：正确姿势 —— 唯一标识 value + Lua 原子释放");
        ManualClock c3 = new ManualClock(0);
        InMemoryLockStorage s3 = new InMemoryLockStorage(c3);
        SafeLock a3 = new SafeLock(s3, c3, "stock:sku1:lock", 1_000);
        check(a3.tryLock(), "A 拿到锁");
        c3.advance(1_001);
        SafeLock b3 = new SafeLock(s3, c3, "stock:sku1:lock", 1_000);
        check(b3.tryLock(), "锁过期后 B 顶上");
        check(a3.unlock() == false, "A 的 finally 释放失败：token 与锁内 value 不匹配 → B 的锁还在");
        check(s3.isHeld("stock:sku1:lock"), "B 的锁完好，临界区仍被 B 独占");
        check(new SafeLock(s3, c3, "stock:sku1:lock", 1_000).tryLock() == false, "C 拿不到锁（没有两把锁并发）");
        check(b3.unlock(), "B 业务结束用自己 token 释放成功 —— 一切恢复正常");

        System.out.println("场景四：看门狗 —— 业务比锁长时主动续期（Redisson watchdog 语义）");
        ManualClock c4 = new ManualClock(0);
        InMemoryLockStorage s4 = new InMemoryLockStorage(c4);
        SafeLock w = new SafeLock(s4, c4, "seckill:sku1:lock", 500); // 锁寿命只有 500ms
        check(w.tryLock(), "持有者拿到锁（ttl=500ms）");
        c4.advance(300);
        // 业务进行到一半：还没结束，但锁还剩 200ms —— 启动「看门狗」续期
        check(s4.expireIfOwner("seckill:sku1:lock", w.token(), 500),
                "业务未完时看门狗续期成功（token 校验通过，锁再续 500ms）");
        c4.advance(400); // 原到期点已过
        check(s4.isHeld("seckill:sku1:lock"), "超过原 ttl 仍持有（看门狗续期中，长任务不会中途丢锁）");
        check(w.unlock(), "业务真正结束后才释放 —— 续期期间没有第二把锁插进来");

        System.out.println();
        System.out.println("全部自检通过。对照主文档 3.4/4.4：");
        System.out.println("  - 拿锁必须 SET NX EX ttl；释放必须 Lua 校验 value（Redisson/Jedis 都这么写）");
        System.out.println("  - 看门狗只是「尽量续」，进程崩溃时 TTL 依然兜底释放 —— 锁永远不会永久死锁");
        System.out.println("  - 分布式下不信任任何本地时钟与进程状态；锁的每一次读写都以 Redis 服务端为准");
    }
}
