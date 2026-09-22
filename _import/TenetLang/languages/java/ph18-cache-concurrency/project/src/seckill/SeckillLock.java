// project/src/seckill/SeckillLock.java —— 秒杀用「分布式锁」语义后端（模拟 Redis SETNX + Lua 释放）
// 教学映射：真实 Redis 写法（主文档 3.4/examples/ex04）——
//   拿锁  = SET skuId token NX EX leaseMs
//   释放  = Lua: if get(skuId)==token then del(skuId) end
//   看门狗 = 持有者周期续期（本 demo 用足够大的租约 + 短临界区代替续期，长任务场景见 ex04 场景四）
// 本文件用内存 Map 实现同一协议语义：value=token（唯一标识）、租约到期自动让位、释放校验 token。
// 说明：单 JVM 内它退化为进程内锁；多实例部署时同一把锁落在共享 Redis 上语义完全一致 ——
//       这就是「秒杀库存扣减为什么要在分布式锁里做」的原因（防止多实例并发扣成负数）。
package seckill;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ThreadLocalRandom;

/** 模拟分布式锁：按 sku 串行化「检查库存 → 扣减」，防止多实例并发扣超 */
final class SeckillLock {

    /** 锁后端抽象：LockBackend 的内存实现 ≈ Redis 的 key 操作 */
    interface LockBackend {
        boolean setIfAbsent(String key, String value, long ttlMs);

        boolean compareAndDelete(String key, String value); // Lua: value 对得上才删
    }

    /** 内存实现：懒过期（读时判断 expiresAt），把 Redis 服务端过期语义演出来 */
    static final class InMemoryBackend implements LockBackend {
        record Entry(String value, long expiresAt) {
        }

        private final Clock clock;
        private final Map<String, Entry> data = new ConcurrentHashMap<>();

        InMemoryBackend(Clock clock) {
            this.clock = clock;
        }

        @Override
        public synchronized boolean setIfAbsent(String key, String value, long ttlMs) {
            Entry cur = data.get(key);
            long now = clock.now();
            if (cur != null && cur.expiresAt() > now) {
                return false; // 未过期的锁还在
            }
            data.put(key, new Entry(value, now + ttlMs));
            return true;
        }

        @Override
        public synchronized boolean compareAndDelete(String key, String value) {
            Entry cur = data.get(key);
            if (cur == null || !cur.value().equals(value)) {
                return false; // 锁已过期或已是别人的：绝不能删
            }
            data.remove(key);
            return true;
        }

        synchronized boolean isHeld(String key) {
            Entry cur = data.get(key);
            return cur != null && cur.expiresAt() > clock.now();
        }
    }

    private final LockBackend backend;
    private final long leaseMs;

    SeckillLock(LockBackend backend, long leaseMs) {
        this.backend = backend;
        this.leaseMs = leaseMs;
    }

    /**
     * 非阻塞拿锁：成功返回 token（释放时凭 token），失败返回 null。
     * token 用随机串 —— 释放时后端比对 token，绝不会误删别人拿到的锁。
     */
    String tryLock(String key) {
        String token = "lock-" + key + "-" + Thread.currentThread().getName()
                + "-" + ThreadLocalRandom.current().nextLong();
        return backend.setIfAbsent(key, token, leaseMs) ? token : null;
    }

    /** 凭 token 释放（compare-and-delete） */
    void unlock(String key, String token) {
        backend.compareAndDelete(key, token);
    }
}
