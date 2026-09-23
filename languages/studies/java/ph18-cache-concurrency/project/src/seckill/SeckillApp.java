// project/src/seckill/SeckillApp.java —— 秒杀 demo 启动器与验收断言
// 构建与运行（在 project/ 目录下执行）：
//   javac -d out src/seckill/*.java
//   java -cp out seckill.SeckillApp
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：javac 编译通过、运行全部 PASS）
// 场景编排：
//   场景一 300 并发抢 30 件 —— 验证分层防御下的「不超卖 + 库存扣对 + 订单对得上」；
//   场景二 边界语义（幂等 DUPLICATE / 未开始 NOT_STARTED / 限流 LIMIT）单线程确定性验证。
// 生产形态对照（主文档 3.7/5 章）：本 demo 是单 JVM 的「语义版」——
//   ProductCache.L2 / SeckillLock / TokenBucket 的远端载体分别是 Redis SETEX / SETNX+Lua / INCR+Lua；
//   多实例部署时把这三处换成共享 Redis，其余编排代码原样可跑。
package seckill;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/** 秒杀系统 demo：限流 → 幂等 → 缓存 → 锁 → 库存扣减 → 下单 */
final class SeckillApp {

    static void check(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError("自检失败: " + label);
        }
        System.out.println("PASS  " + label);
    }

    public static void main(String[] args) throws InterruptedException {
        ManualClock clock = new ManualClock(0);
        // 入口限流配额放宽（每人 1000 个令牌），压测只压「锁 + 扣减 + 幂等」这几层
        SeckillService seckill = new SeckillService(clock,
                new SeckillLock(new SeckillLock.InMemoryBackend(clock), 30_000),
                1_000, 0);
        seckill.createSeckill("SKU-A", "Tenet 限量模型", 199, 30, 0); // 立即开抢

        System.out.println("场景一：300 并发抢 30 件 —— 分层防御链路（缓存→限流→幂等→锁→扣减）");
        int users = 300;
        ExecutorService pool = Executors.newFixedThreadPool(64);
        CountDownLatch start = new CountDownLatch(1);
        CountDownLatch done = new CountDownLatch(users);
        AtomicInteger success = new AtomicInteger();
        AtomicInteger soldOut = new AtomicInteger();
        AtomicInteger busy = new AtomicInteger();
        for (int i = 0; i < users; i++) {
            String user = "rush-" + i;
            pool.submit(() -> {
                try {
                    start.await();
                    switch (seckill.placeOrder(user, "SKU-A")) {
                        case SUCCESS -> success.incrementAndGet();
                        case SOLD_OUT -> soldOut.incrementAndGet();
                        case BUSY -> busy.incrementAndGet();
                        default -> { /* 压测里不应出现其他结果 */ }
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                } finally {
                    done.countDown();
                }
            });
        }
        start.countDown();
        done.await(15, TimeUnit.SECONDS);
        pool.shutdownNow();

        check(success.get() == 30, "300 并发恰好 30 人抢到（success=" + success.get() + "）");
        check(soldOut.get() + busy.get() == 270,
                "其余 270 人拿到的都是明确的失败语义（SOLD_OUT=" + soldOut.get()
                        + " + BUSY=" + busy.get() + "），不是超卖也不是无响应");
        check(seckill.remainingStock("SKU-A") == 0, "库存精确归零，从未出现负数（无超卖）");
        check(seckill.createdOrders() == 30, "订单数 = 抢到数（30），账实相符");
        check(seckill.productDbLoads() == 1,
                "商品信息被 300 个请求读了 300 次，DB 只回源 1 次（两级缓存 + 单飞把 DB 挡在最后）");

        System.out.println("场景二：边界语义（幂等 / 未开始 / 限流）—— 单线程确定性验证");
        // 幂等：同一用户同一 sku 只下一单
        SeckillService s2 = new SeckillService(clock,
                new SeckillLock(new SeckillLock.InMemoryBackend(clock), 30_000),
                1_000, 0);
        s2.createSeckill("SKU-B", "经典款", 99, 1, 0);
        check(s2.placeOrder("bob", "SKU-B") == SeckillService.Result.SUCCESS, "bob 首抢成功");
        check(s2.placeOrder("bob", "SKU-B") == SeckillService.Result.DUPLICATE, "bob 重复点击 → DUPLICATE（幂等拦截，不二次扣库存）");
        check(s2.remainingStock("SKU-B") == 0, "库存没有被重复扣（幂等层生效）");
        check(s2.placeOrder("carol", "SKU-B") == SeckillService.Result.SOLD_OUT, "carol 抢 → SOLD_OUT（1 件已被 bob 买走）");

        // 未开始：开抢时间在未来
        SeckillService s3 = new SeckillService(clock,
                new SeckillLock(new SeckillLock.InMemoryBackend(clock), 30_000),
                1_000, 0);
        s3.createSeckill("SKU-C", "预售款", 299, 100, clock.now() + 60_000);
        check(s3.placeOrder("alice", "SKU-C") == SeckillService.Result.NOT_STARTED, "未到开抢时间 → NOT_STARTED");
        clock.advance(60_001);
        check(s3.placeOrder("alice", "SKU-C") == SeckillService.Result.SUCCESS, "开抢时间到 → 正常抢购");

        // 限流：每用户令牌容量 1（rate=0 不补充），第二次请求被 LIMIT 挡下
        SeckillService s4 = new SeckillService(clock,
                new SeckillLock(new SeckillLock.InMemoryBackend(clock), 30_000),
                1, 0);
        s4.createSeckill("SKU-D", "限量鞋", 599, 100, 0);
        check(s4.placeOrder("fast", "SKU-D") == SeckillService.Result.SUCCESS, "第一个请求放行");
        check(s4.placeOrder("fast", "SKU-D") == SeckillService.Result.LIMIT, "同一用户连点第二个 → LIMIT（入口限流兜住点击风暴）");
        check(s4.placeOrder("fast", "SKU-D") == SeckillService.Result.LIMIT, "第三个仍被限流（令牌不补充，rate=0）");

        System.out.println();
        System.out.println("全部自检通过。分层防御链路回顾（对照主文档 5 章）：");
        System.out.println("  [入口]  每用户令牌桶限流    → 挡点击风暴（LIMIT）");
        System.out.println("  [接入]  user+sku 幂等占位    → 挡重复下单（DUPLICATE）");
        System.out.println("  [缓存]  两级缓存读商品       → 挡 DB（商品元数据 300 次读只回源 1 次）");
        System.out.println("  [锁]    per-sku 分布式锁     → 挡多实例并发扣减（BUSY 可重试）");
        System.out.println("  [存储]  CAS 原子扣库存 + 订单 → 不超卖、账实相符（SUCCESS/SOLD_OUT）");
        System.out.println("生产化缺口：真实 Redis（SETNX+Lua）、MQ 异步下单、秒杀按钮置灰与回滚对账 —— 见 project/README 扩展方向");
    }
}
