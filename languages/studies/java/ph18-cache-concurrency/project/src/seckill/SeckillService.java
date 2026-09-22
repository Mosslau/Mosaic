// project/src/seckill/SeckillService.java —— 秒杀核心编排（roadmap ph18 推荐项目一：秒杀系统 demo）
// 高并发分层防御链（对应主文档 5 章「从入口到存储的分层防御」）：
//   ① 入口限流   —— 每用户令牌桶（TokenBucket）：把单个用户的点击速率压到可控水位
//   ② 幂等防重   —— 用户+sku 唯一占位（OrderBook.reserve，模拟数据库唯一索引）
//   ③ 缓存读    —— 商品信息走两级缓存（ProductCache），预热后 DB 只被读一次
//   ④ 分布式锁  —— 按 sku 拿锁（SeckillLock，模拟 Redis SETNX+Lua）：多实例并发扣减被串行化
//   ⑤ 原子扣减  —— 锁内 CAS 扣库存（Stock.tryDeduct，等价 Redis Lua if stock>=1 then DECRBY）
// 失败语义：SUCCESS / SOLD_OUT / DUPLICATE / LIMIT / BUSY / NOT_STARTED，见 Result 枚举。
package seckill;

import java.util.EnumMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/** 秒杀服务：把限流、幂等、缓存、锁、扣库存按顺序编排成一条并发防御链 */
final class SeckillService {

    /** 一次抢购的结局 */
    enum Result {
        SUCCESS,     // 抢到并已扣库存
        SOLD_OUT,    // 没货（库存不足，占位已回滚，可稍后重试）
        DUPLICATE,   // 同一用户同一 sku 已下过单（幂等拦截）
        LIMIT,       // 被入口限流挡住（点击过快）
        BUSY,        // 锁竞争超时（临界区太忙，重试可能成功）
        NOT_STARTED  // 秒杀还没开始
    }

    /** 库存：CAS 保证永不为负（不会超卖） */
    static final class Stock {
        private final AtomicInteger remaining;
        private final int initial;

        Stock(int initial) {
            this.remaining = new AtomicInteger(initial);
            this.initial = initial;
        }

        /** CAS 自旋扣 qty；失败返回 false（库存不足） */
        boolean tryDeduct(int qty) {
            while (true) {
                int cur = remaining.get();
                if (cur < qty) {
                    return false;
                }
                if (remaining.compareAndSet(cur, cur - qty)) {
                    return true;
                }
            }
        }

        int remaining() {
            return remaining.get();
        }
    }

    /** 订单表：reserve 幂等占位（唯一约束），finalize 记账（下单成功才累计） */
    static final class OrderBook {
        private final Map<String, Boolean> seats = new ConcurrentHashMap<>();
        private final AtomicInteger created = new AtomicInteger();

        /** 首次占位 true；重复 false（user#sku 唯一） */
        boolean reserve(String userAndSku) {
            return seats.putIfAbsent(userAndSku, Boolean.TRUE) == null;
        }

        void release(String userAndSku) {
            seats.remove(userAndSku); // 无货/未开始等失败路径回滚占位
        }

        void finalizeOrder(String userAndSku) {
            created.incrementAndGet();
        }

        int created() {
            return created.get();
        }

        int reservedSeats() {
            return seats.size();
        }
    }

    private final Clock clock;
    private final SeckillLock lock;
    private final ProductCache productCache;
    private final Map<String, Stock> stocks = new ConcurrentHashMap<>();
    private final Map<String, TokenBucket> userBuckets = new ConcurrentHashMap<>();
    private final OrderBook orderBook = new OrderBook();
    private final int perUserCapacity;      // 每人同时最多发起几个请求（未补充前）
    private final double perUserRatePerSec; // 每人令牌补充速率
    private final Map<String, ProductCache.Product> productDb; // 供 ProductCache 回源
    private final AtomicInteger productDbLoads = new AtomicInteger();
    private final EnumMap<Result, AtomicInteger> counts = new EnumMap<>(Result.class);
    private static final int LOCK_MAX_TRIES = 50_000; // 锁竞争自旋上限

    SeckillService(Clock clock, SeckillLock lock, int perUserCapacity, double perUserRatePerSec) {
        this.clock = clock;
        this.lock = lock;
        this.perUserCapacity = perUserCapacity;
        this.perUserRatePerSec = perUserRatePerSec;
        this.productDb = new ConcurrentHashMap<>();
        this.productCache = new ProductCache(clock, productDb, productDbLoads);
        for (Result r : Result.values()) {
            counts.put(r, new AtomicInteger());
        }
    }

    /** 上架一个秒杀 sku：商品信息 + 库存 + 开抢时间 */
    void createSeckill(String skuId, String name, int price, int stock, long startAtMs) {
        productDb.put(skuId, new ProductCache.Product(skuId, name, price, startAtMs));
        stocks.put(skuId, new Stock(stock));
    }

    /** 抢购主入口（顺序即分层防御顺序：限流 → 幂等 → 缓存 → 锁 → 扣减） */
    Result placeOrder(String userId, String skuId) {
        ProductCache.Product p = productCache.get(skuId);           // ③ 缓存读（miss 才碰 DB）
        if (p == null) {
            return fail(Result.SOLD_OUT);                            // 无此 sku：教学简化为 SOLD_OUT
        }
        if (clock.now() < p.seckillStartAt()) {
            return fail(Result.NOT_STARTED);                         // 未开抢
        }
        if (!userBucket(userId).tryAcquire()) {                      // ① 入口限流
            return fail(Result.LIMIT);
        }
        String seat = userId + "#" + skuId;
        if (!orderBook.reserve(seat)) {                              // ② 幂等：同用户同 sku 只下一单
            return fail(Result.DUPLICATE);
        }
        // ④+⑤ 拿锁后在锁内做「检查库存 → CAS 扣减 → 记账」，多实例也不会扣超
        String token = spinLock(skuId);
        if (token == null) {
            orderBook.release(seat);                                 // 抢锁失败：释放占位
            return fail(Result.BUSY);
        }
        try {
            Stock stock = stocks.get(skuId);
            if (!stock.tryDeduct(1)) {                               // ⑤ 原子扣减失败 = 没货
                orderBook.release(seat);
                return fail(Result.SOLD_OUT);
            }
            orderBook.finalizeOrder(seat);                           // 下单成功
            return fail(Result.SUCCESS);
        } finally {
            lock.unlock(skuId, token);                               // 凭 token 释放（不会误删别人的锁）
        }
    }

    /** 拿锁的自旋重试：临界区很短（一次 CAS + 记账），稍等就能抢到 */
    private String spinLock(String skuId) {
        for (int i = 0; i < LOCK_MAX_TRIES; i++) {
            String token = lock.tryLock(skuId);
            if (token != null) {
                return token;
            }
            Thread.onSpinWait(); // 让出 CPU 总线等待，避免自旋烧空核
        }
        return null;
    }

    private TokenBucket userBucket(String userId) {
        return userBuckets.computeIfAbsent(userId,
                k -> new TokenBucket(clock, perUserCapacity, perUserRatePerSec));
    }

    private Result fail(Result r) {
        counts.get(r).incrementAndGet();
        return r;
    }

    int count(Result r) {
        return counts.get(r).get();
    }

    int remainingStock(String skuId) {
        return stocks.get(skuId).remaining();
    }

    int createdOrders() {
        return orderBook.created();
    }

    int productDbLoads() {
        return productDbLoads.get();
    }
}
