# ph18 阶段项目：秒杀系统 demo

## 需求

roadmap「18. 缓存与高并发阶段」推荐项目之一——**秒杀系统 demo**，把本阶段四道练习的零件（热点缓存 sol-01、接口限流 sol-02、库存扣减 sol-03、批量写入 sol-04）按一条完整的**高并发分层防御链**串起来：

**每用户限流（入口）→ user+sku 幂等占位（防重复下单）→ 两级缓存读商品（挡 DB）→ per-sku 分布式锁（挡多实例并发扣减）→ CAS 原子扣库存 → 订单记账（账实相符）**。

并发场景验收：300 个线程同时抢 30 件库存，恰好 30 人成功、无超卖、无重复扣、库存与订单对得上、商品信息 300 次读只回源 DB 1 次。生产形态与 demo 的差距见「扩展方向」。

## 目录结构

```
project/
├── README.md
└── src/seckill/
    ├── SeckillApp.java      # 启动器：场景一（300 并发压测）+ 场景二（边界语义），全部 PASS 自检
    ├── SeckillService.java  # 核心编排：限流→幂等→缓存→锁→扣库存（本项目的骨干）
    ├── ProductCache.java    # 两级缓存（L1 本地 / L2 远端）+ 单飞回源
    ├── SeckillLock.java     # 分布式锁语义后端（SETNX + token 校验释放，模拟 Redis）
    ├── TokenBucket.java     # 入口限流（每用户令牌桶）
    └── SimClock.java        # 虚拟时钟（演示确定性断言用）
```

## 技术栈与验证环境

- OpenJDK 17（`javac -version -> 17.x`），**无第三方依赖、纯 Java 17 多文件工程**——核心语义全部单 JVM 可跑
- 依赖真实 Redis 的生产形态不在本工程内（对应实现方案在 examples/ex01 与扩展方向），需 Redis 的部分标注「未在本环境验证」
- **已验证**：OpenJDK 17.0.18 本机实测 `javac` 编译通过、`java seckill.SeckillApp` 运行全部 PASS（BUSY=0、success=30、库存精确归零、DB 只回源 1 次）

## 构建与运行（已验证）

```bash
# 1. 编译（在 project/ 目录下执行，产物输出到 out/）
javac -d out src/seckill/*.java
# 2. 运行验收自检
java -cp out seckill.SeckillApp
# 3. 清理
rm -rf out
```

运行输出即验收报告（每行 `PASS ...` 都是一条验收标准），末尾会打印分层防御链路回顾。

## 功能清单

- [x] **入口限流**：每用户令牌桶（容量限突发），用户连点风暴被 LIMIT 挡下（场景二验证）
- [x] **幂等防重**：`user#sku` 唯一占位（`putIfAbsent` ≈ 数据库唯一索引），重复点击返回 DUPLICATE 且不二次扣库存
- [x] **两级缓存读商品**：L1(本地) → L2(远端) → DB，miss 单飞回源；预热后 300 次读 DB 只回源 1 次
- [x] **分布式锁**：按 sku 拿锁（模拟 `SET key token NX EX ttl`），释放凭 token 做 compare-and-delete（不误删他人锁）
- [x] **原子扣库存**：锁内 CAS 扣减（等价 Redis Lua `if stock>=1 then DECRBY`），永不为负、不超卖
- [x] **边界语义**：SUCCESS / SOLD_OUT / DUPLICATE / LIMIT / NOT_STARTED 五种结果语义清晰可断言
- [x] **账实相符**：`成功数 + 剩余库存 = 初始库存`、`订单数 = 成功数`（对账是上线后的例行检查）

## 验收标准

- **不超卖**：300 并发抢 30 件 → `success == 30`，库存从 30 精确到 0（无负数），订单数 == 30
- **失败语义明确**：其余 270 人拿到 SOLD_OUT 或 BUSY（可重试），不是超卖也不是无响应
- **幂等生效**：同一用户重复点击只下一单（DUPLICATE 不扣库存）；bob 买走唯一一件后 carol 拿到 SOLD_OUT
- **限流生效**：每用户容量 1 时，同一用户连点第 2、3 次都被 LIMIT 挡下
- **缓存挡 DB**：`productDbLoads() == 1`（300 次商品读只有 1 次回源）
- **时间边界**：未到开抢时间返回 NOT_STARTED，到点后正常放行
- **能画出防御链并说出每层挡什么**：限流挡点击风暴 → 幂等挡重复下单 → 缓存挡 DB → 锁挡并发扣减 → CAS+订单保证不超卖与账实相符（对照主文档 5 章）

## 与真实生产形态的差距（扩展方向）

| demo 内 | 生产形态 | 说明 |
|---------|---------|------|
| `SeckillLock.InMemoryBackend` | Redis `SETNX + Lua`（examples/ex04、ex01 第 7/8 步） | 多实例共享同一 Redis 才叫「分布式」锁；本 demo 单 JVM 只是语义版 |
| `TokenBucket`（JVM 内） | Redis `INCR + EXPIRE` 或 Lua 令牌桶 | 多实例入口限流计数必须全局一致（主文档 3.5） |
| `ProductCache.L2`（内存 Map） | Redis `SETEX` | 见 examples/ex01 第 6 步 Cache-Aside |
| 扣库存同步在请求线程内 | 扣库存 + MQ 异步下单（ph17） | 下单明细写库、发通知异步化，请求只等「预扣成功」 |
| 秒杀结束靠库存=0 | 本地标记 + 定时器回源 | 主文档 3.7 的「本地标记」优化：库存为 0 后本地直接拒，别再打 Redis |
| 手动时钟/断言自检 | 单元测试 + 压测（jmeter/wrk） | demo 的自检换成 JUnit（ph12）与真实压测脚本 |

**为什么本 demo 是纯 Java 而非 Spring Boot 工程**：秒杀的核心难点全在「并发防御协议」本身（限流/幂等/锁/扣减的语义与顺序），而这些协议与 Web 框架无关；单 JVM 语义版让每个学习者都能在无 Redis 环境实测跑通并看到确定性断言。要升级成可部署服务：把三个「模拟后端」换成 Redis（坐标与命令见 examples/ex01），再包一层 Spring Boot Controller + MQ（参照 ph14/ph17 的工程结构），即可作为秒杀服务雏形。

## 端口与清理

无网络端口。`rm -rf out` 清理编译产物。
