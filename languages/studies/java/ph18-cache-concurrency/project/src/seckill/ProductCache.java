// project/src/seckill/ProductCache.java —— 秒杀商品信息的两级缓存 + 单飞回源
// 教学映射：对应主文档 3.2/3.3 与 examples/ex07 —— L1(本地) 最快但不跨实例、L2(远端) 共享；
//           秒杀里商品信息（名称/价格/开始时间）是典型的「读多写极少」，先预热再挡流量，DB 只该被读一次。
//           写路径：DB 更新 → 删 L2 → 失效广播（本 demo 数据不变，不演示更新，见 ex07 的完整版）。
package seckill;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/** 秒杀商品两级缓存：L1(本地) → L2(远端) → DB；并发 miss 单飞 */
final class ProductCache {
    /** 商品元数据 */
    record Product(String skuId, String name, int price, long seckillStartAt) {
    }

    /** 带 TTL 的条目 */
    record Entry(Object value, long expiresAt) {
    }

    private final Clock clock;
    private final Map<String, Product> db; // 模拟数据库（秒杀前把商品行放进来的「预热数据源」）
    private final java.util.concurrent.atomic.AtomicInteger dbLoads;
    private final Map<String, Entry> l1 = new ConcurrentHashMap<>();
    private final Map<String, Entry> l2 = new ConcurrentHashMap<>();
    private final Map<String, Object> monitors = new ConcurrentHashMap<>();

    ProductCache(Clock clock, Map<String, Product> db, java.util.concurrent.atomic.AtomicInteger dbLoads) {
        this.clock = clock;
        this.db = db;
        this.dbLoads = dbLoads;
    }

    /** 读商品（返回 null = 无此 sku）；命中 L1/L2 不碰 DB */
    Product get(String skuId) {
        Object m = monitors.computeIfAbsent(skuId, k -> new Object());
        synchronized (m) { // 单飞：并发 miss 只回源一次（防止商品信息冷启动被击穿，主文档 3.3）
            Entry e = l1.get(skuId);
            long now = clock.now();
            if (e != null && e.expiresAt > now) {
                return (Product) e.value();
            }
            e = l2.get(skuId);
            if (e != null && e.expiresAt > now) {
                l1.put(skuId, e); // 远端命中 → 回填本地
                return (Product) e.value();
            }
            dbLoads.incrementAndGet(); // 两级都 miss 才回源 DB（期望：预热后整场秒杀只发生一次）
            Product p = db.get(skuId);
            if (p != null) {
                long ttl = now + 120_000;
                l2.put(skuId, new Entry(p, ttl)); // 远端 TTL 长
                l1.put(skuId, new Entry(p, now + 30_000)); // 本地 TTL 短保新鲜
            }
            monitors.remove(skuId); // 必须回填后再移除（防双检失效，约定同 exercises/sol-01）
            return p;
        }
    }
}
