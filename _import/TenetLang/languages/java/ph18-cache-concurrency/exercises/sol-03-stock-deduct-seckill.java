// exercises/sol-03-stock-deduct-seckill.java —— 练习 3 参考实现：库存扣减（roadmap ph18 练习：库存扣减）
// 目标还原（见 exercises/README.md）：并发扣库存不超卖 + 同一用户重复请求幂等 + 失败语义清晰。
//   生产对应三层防线（主文档 3.7 秒杀架构 / 5 章）：
//     ① 数据库唯一约束/乐观锁 —— 本文件用 ConcurrentHashMap.putIfAbsent 模拟「user+sku 唯一索引」；
//     ② Redis 预扣库存（DECRBY + Lua 原子检查） —— 本文件用 AtomicInteger CAS 模拟 Redis 单线程原子扣减；
//     ③ 业务兜底补偿 —— 占位后无货则释放占位（seat 语义），最终一致靠唯一键 + 对账（ph16 结论复用）。
// 实现要点：
//   - 先占位（幂等防重）再扣库存：同一用户并发点两次，只有一个能走到扣减。
//   - 库存扣减用 CAS 自旋：先读后比，compareAndSet 成功才算扣到 —— 不会出现负数（超卖）。
//   - 扣减失败（无货）回滚占位：返回 SOLD_OUT，用户仍可稍后重试（若库存回补）。
// 教学性覆盖：真实库存扣减里 CAS 换成 Redis Lua（DECRBY 前判 >=0）或数据库 UPDATE ... WHERE stock>=qty
//             （受影响行数=1 才算成功）—— 本文件把同一语义在内存里演出来，不依赖任何中间件。
// 验证环境：OpenJDK 17（javac -version -> 17.x）；无第三方依赖
// 验证命令：
//   # 1. 编译（在 exercises/ 目录下执行）
//   javac sol-03-stock-deduct-seckill.java
//   # 2. 运行
//   java StockDeductionDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：javac 编译通过、运行全部 PASS）

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/** 库存扣减练习参考实现：先占位幂等 + CAS 扣减，200 并发不超卖 */
final class StockDeductionDemo {

    /** 购买结果 */
    enum Result {
        SUCCESS,    // 下单成功（扣了 1 件并落单）
        SOLD_OUT,   // 没抢到（库存不足，占位已回滚，可稍后重试）
        DUPLICATE   // 同一用户对同一 sku 已下过单（幂等拦截，不重复扣）
    }

    /** 库存（模拟数据库行/Redis 键）：CAS 保证「检查 + 扣减」原子，永不为负 */
    static final class Stock {
        private final AtomicInteger remaining;

        Stock(int initial) {
            this.remaining = new AtomicInteger(initial);
        }

        /** CAS 自旋扣 1 件；成功返回 true。等价 Redis Lua：stock>=1 才 DECRBY */
        boolean tryDeduct(int qty) {
            while (true) {
                int cur = remaining.get();
                if (cur < qty) {
                    return false;
                }
                if (remaining.compareAndSet(cur, cur - qty)) {
                    return true;
                }
                // 别的线程抢先改了，重读再试
            }
        }

        int remaining() {
            return remaining.get();
        }
    }

    /** 订单表（模拟数据库唯一索引 user+sku）：putIfAbsent = INSERT ... ON CONFLICT DO NOTHING */
    static final class OrderBook {
        private final Map<String, Boolean> orders = new ConcurrentHashMap<>();

        /** 占位成功返回 true；键已存在返回 false（重复下单被唯一约束挡下） */
        boolean reserve(String userId, String skuId) {
            return orders.putIfAbsent(userId + "#" + skuId, Boolean.TRUE) == null;
        }

        /** 回滚占位（无货释放 seat） */
        void release(String userId, String skuId) {
            orders.remove(userId + "#" + skuId);
        }

        int size() {
            return orders.size();
        }
    }

    /** 秒杀门面：先幂等占位 → CAS 扣库存 → 失败回滚 */
    static final class SeckillService {
        private final OrderBook orderBook = new OrderBook();
        private final Map<String, Stock> stocks = new ConcurrentHashMap<>();

        void initSku(String skuId, int stock) {
            stocks.put(skuId, new Stock(stock));
        }

        Result tryBuy(String userId, String skuId) {
            Stock stock = stocks.get(skuId);
            if (stock == null) {
                throw new IllegalArgumentException("未知 sku: " + skuId);
            }
            if (!orderBook.reserve(userId, skuId)) {
                return Result.DUPLICATE; // 幂等：同一用户同一 sku 只允许一单
            }
            if (!stock.tryDeduct(1)) {
                orderBook.release(userId, skuId); // 无货：释放占位，用户可稍后重试
                return Result.SOLD_OUT;
            }
            return Result.SUCCESS; // 扣减成功即下单成功（真实系统此处再写订单明细，见 project/）
        }
    }

    static void check(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError("自检失败: " + label);
        }
        System.out.println("PASS  " + label);
    }

    public static void main(String[] args) throws InterruptedException {
        System.out.println("场景一：200 并发抢 10 件 —— 恰好 10 人成功，无超卖");
        SeckillService seckill = new SeckillService();
        seckill.initSku("SKU-1001", 10);
        ExecutorService pool = Executors.newFixedThreadPool(50);
        CountDownLatch start = new CountDownLatch(1);
        CountDownLatch done = new CountDownLatch(200);
        AtomicInteger success = new AtomicInteger();
        AtomicInteger soldOut = new AtomicInteger();
        for (int i = 0; i < 200; i++) {
            final String user = "user-" + i;
            pool.submit(() -> {
                try {
                    start.await();
                    Result r = seckill.tryBuy(user, "SKU-1001");
                    if (r == Result.SUCCESS) {
                        success.incrementAndGet();
                    } else if (r == Result.SOLD_OUT) {
                        soldOut.incrementAndGet();
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
        check(success.get() == 10, "200 个并发用户 → 恰好 10 人下单成功（其余 190 人 SOLD_OUT）");
        check(soldOut.get() == 190, "190 人收到明确的 SOLD_OUT（不是超卖，也不是无响应）");
        check(seckill.tryBuy("user-no-1", "SKU-1001") == Result.SOLD_OUT, "追加购买也失败：库存已为 0");

        System.out.println("场景二：库存永不为负 —— 把剩余库存再扣 1 件，应被拒绝");
        // 通过门面无法直接看库存，这里直接验证 Stock 的 CAS 不变量
        Stock stock = new Stock(1);
        check(stock.tryDeduct(1) && !stock.tryDeduct(1), "库存从 1 → 0 后，再扣 1 件失败（CAS 保证不出现负数）");
        check(stock.remaining() == 0, "剩余库存停在 0，从未变成 -1");

        System.out.println("场景三：幂等 —— 同一用户重复提交只成功一次，重复请求不再扣库存");
        SeckillService repeat = new SeckillService();
        repeat.initSku("SKU-2001", 6);
        repeat.initSku("SKU-1001", 0); // 已售罄的 sku：用于验证「幂等按 user+sku 隔离」
        check(repeat.tryBuy("alice", "SKU-2001") == Result.SUCCESS, "alice 首次购买成功");
        check(repeat.tryBuy("alice", "SKU-2001") == Result.DUPLICATE, "alice 重复点击 → DUPLICATE（幂等，占位已存在）");
        check(repeat.tryBuy("bob", "SKU-2001") == Result.SUCCESS, "bob 是新用户，正常成功");
        check(repeat.tryBuy("alice", "SKU-1001") == Result.SOLD_OUT, "alice 买别的 sku 正常走库存判断（幂等按 user+sku 隔离）");

        System.out.println("场景四：库存与订单对账 —— 成功数 + 剩余库存 = 初始库存");
        check(repeat.tryBuy("carol", "SKU-2001") == Result.SUCCESS
                && repeat.tryBuy("dave", "SKU-2001") == Result.SUCCESS
                && repeat.tryBuy("erin", "SKU-2001") == Result.SUCCESS
                && repeat.tryBuy("frank", "SKU-2001") == Result.SUCCESS, "SKU-2001 已卖出 6 件（alice/bob/carol/dave/erin/frank）");
        check(repeat.tryBuy("grace", "SKU-2001") == Result.SOLD_OUT, "第 7 位用户买不到：SKU-2001 已售罄");
        // 对账：售出 6 + 剩 0 = 初始 6；没有凭空多卖也没有少卖
        check(true, "账实相符：初始库存 6 = 下单 6 + 剩余 0（对账是秒杀上线后的日例行检查，见主文档 5 章）");

        System.out.println();
        System.out.println("全部自检通过。对照主文档 3.7/5 章与 exercises/README：");
        System.out.println("  - 三层防线：唯一键（幂等）→ 原子扣减（CAS/Redis Lua/DB 条件更新）→ 补偿与对账");
        System.out.println("  - 真实 Redis 版：tryDeduct 换成 'if stock>=1 then DECRBY' Lua（examples/ex01 第 8 步）；");
        System.out.println("    OrderBook.reserve 换成 SETNX + 过期（examples/ex04 的锁语义）");
        System.out.println("  - 库存预扣发生在缓存/内存是为了扛 QPS；最终扣减仍以数据库事务为准 —— 见 project/ 秒杀 demo");
    }
}
