# ph18 缓存与高并发 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> **与 roadmap「18. 缓存与高并发阶段」练习小节的对应**：四题一一对应 roadmap 列的四个练习——练习 1 = 热点数据缓存、练习 2 = 接口限流、练习 3 = 库存扣减、练习 4 = 批量写入优化。四题合起来是「高并发防护」的一条技能线：多级缓存与单飞（1）→ 入口限流（2）→ 库存原子扣减与幂等（3）→ 写链路的批量优化（4），做完即具备本阶段 project（秒杀系统 demo）的全部零件。
> **验证状态**：四份参考实现均为纯 Java 17 单文件（内部用虚拟时钟 + 内存存储模拟 Redis/DB 语义），已在 OpenJDK 17.0.18 本机实测全部 PASS（命令 `javac sol-0X-*.java && java <主类名>`，主类名见各文件头）；生产落地点（Redis Lua、Caffeine、Jedis Pipeline 等）见主文档 3.x 与 examples/README，未在本环境实测的部分一律标注「未在本环境验证」。

四题参考实现与生产能力的映射速查：

| 练习 | 参考实现主类 | 生产落地点（主文档） | examples 参照 |
|------|------|---------------------|------|
| 1 热点数据缓存 | HotKeyCacheDemo | L1=Caffeine（3.2）、L2=Redis（3.1）、单飞防击穿（3.3）、热点识别（3.3） | ex02/ex03/ex07、sol 里同款单飞见 ex03 |
| 2 接口限流 | InterfaceRateLimitDemo | 令牌桶/固定窗口算法（3.5）、分布式限流 Redis+Lua（3.5）、网关治理（ph16 Sentinel） | ex05 |
| 3 库存扣减 | StockDeductionDemo | 唯一约束幂等（3.6）、Redis Lua 原子扣减（3.3/3.7）、对账兜底（5 章） | ex01 第 8 步、ex04 |
| 4 批量写入优化 | BatchWriteOptimizationDemo | JDBC addBatch/批量 INSERT、Redis Pipeline/MSET（3.9）、异步化（3.9） | ex01（Redis 批量命令） |

## 练习 1：热点数据缓存（★★）

**目标**：实现两级读缓存（本地 L1 + 远端 L2）+ 并发 miss 单飞 + 热点 key 识别，理解「缓存分层是消费链路的下一道防线」（ph17 主文档预告的落点）。
**要求**：

- 读路径：`L1 → L2 → DB`（Cache-Aside），miss 时逐级回填；两个缓存的 TTL 可独立配置
- 单飞：同一 key 的并发 miss 只允许一个线程回源，其余线程等结果（提示：per-key monitor + 双检，参照 examples/ex03 的 singleFlight 开关）
- 热点识别：滑动时间窗内访问数 ≥ 阈值即把 key 标记为热点，提供 `isHot(key)` 查询（识别后做什么保护——短 TTL、独立副本——在注释里写出思路即可）
- 不许用第三方缓存库（自己用 ConcurrentHashMap + TTL 实现两层）
- 用虚拟时钟测 TTL：L1 过期后 L2 应兜底、两级都过期才回源

**验收**：16 线程并发读同一冷 key，DB 只回源 1 次；200 次后续读 DB 零访问；L1 先过期时 DB 仍零访问；两级都过期后回源计数 +1；访问量超阈值后 `isHot==true`、低访问 key 不误标。参考实现（sol-01）实测全部 PASS，验证命令：`javac sol-01-hot-key-cache.java && java HotKeyCacheDemo`。

## 练习 2：接口限流（★★★）

**目标**：实现「每调用方配额 + 全局总量」的键控限流器，理解为什么只做键控会被「换 key」绕过、以及限流器对象的内存要有界。
**要求**：

- 每 key 一个独立配额（令牌桶：容量限突发、速率限均值，算法可参照 examples/ex05 的 TokenBucket）
- 全局总量桶再兜一层：总量到顶时无论哪个 key 都拒绝
- 空闲回收：超过 idleMs 未访问的 key 可被清理（惰性或显式 `pruneIdle()`），内存有界
- 所有方法线程安全（并发 200 线程抢同一 key 配额不得超放）
- 说明分布式部署时如何把桶搬进 Redis（用 Lua 保证「取令牌+更新」原子，写出思路即可，不用真连 Redis）

**验收**：用户 A 刷爆自己配额不影响用户 B；换 30 个新 key 也只放行全局总量的 20 次；200 线程并发抢同一 key 恰好放行容量数（0 超放）；空闲键能被回收、冷 key 回归自动重建。参考实现（sol-02）实测全部 PASS，验证命令：`javac sol-02-interface-rate-limit.java && java InterfaceRateLimitDemo`。

## 练习 3：库存扣减（★★★）

**目标**：并发扣库存不超卖 + 同一用户重复请求幂等 + 失败语义清晰，体会「先占位幂等 → 原子扣减 → 失败回滚」的编排。
**要求**：

- 幂等：同一 `userId + skuId` 只允许下一单（用 `putIfAbsent` 模拟数据库唯一约束），重复请求返回 DUPLICATE
- 不超卖：库存扣减必须原子——用 CAS 自旋（`AtomicInteger.compareAndSet`）实现，禁止出现负数
- 失败语义：无货返回 SOLD_OUT 并回滚占位（用户可稍后重试）；成功返回 SUCCESS
- 参考实现的 `tryDeduct` 在注释里写明它等价于哪种真实写库姿势（Redis Lua `if stock>=1 then DECRBY`，或 SQL `UPDATE ... SET stock=stock-1 WHERE stock>=1` 受影响行数判定）
- 说明为什么「先扣库存后下单」和「先下单后扣库存」各有什么坑（提示：超卖 / 无货却生成订单）

**验收**：200 并发抢 10 件库存，恰好 10 人 SUCCESS、190 人 SOLD_OUT；库存永不为负；同一用户重复提交只成功一次；「成功数 + 剩余库存 = 初始库存」账实相符。参考实现（sol-03）实测全部 PASS，验证命令：`javac sol-03-stock-deduct-seckill.java && java StockDeductionDemo`。

## 练习 4：批量写入优化（★★）

**目标**：对同一批写操作比较「逐条写 / 攒批写 / 管道写」的往返次数，验证最终落库状态一致，理解优化的是「往返等待」而不是「语义」。
**要求**：

- 造 500 条写操作（250 个 key，每个写两次 = 覆盖语义），分别用三种路径写入同一个「远端存储」
- 计量两个数字：`executedOps`（服务端实际执行条数）与 `roundTrips`（客户端等服务器响应的次数）
- 攒批写：buffer 攒满 100 条才发一批，自己实现 flush；管道写：把整批装进 1 趟往返
- 断言：三条路径 `executedOps` 都是 500、`roundTrips` 分别是 500 / 5 / 1，且最终存储快照完全一致（重复 key 覆盖顺序保持）
- 用注释说明真实世界对应物：JDBC addBatch、数据库批量 INSERT、Redis Pipeline / MSET、MQ 批量投递

**验收**：三路最终状态 `Map` 相等（顺序一致）；覆盖语义保持（同 key 只留最后一次值）；输出对照表 roundTrips 500→5→1。参考实现（sol-04）实测全部 PASS，验证命令：`javac sol-04-batch-write-optimization.java && java BatchWriteOptimizationDemo`。

## 完成后

做完四题继续到 [`project/`](../project/)：秒杀系统 demo 会把练习 1~4 的零件（多级缓存、限流、幂等、库存扣减）按「入口 → 缓存 → 锁 → 扣减 → 下单」串成一条完整的并发防御链。
