# ph18 缓存与高并发 示例

> 七个示例对应主文档「3. 语法与参数」主线：Redis 数据结构与缓存（ex01）→ Caffeine 本地缓存（ex02）→ 缓存穿透/击穿/雪崩防护（ex03，纯 Java）→ 分布式锁语义（ex04，纯 Java）→ 限流算法（ex05，纯 Java）→ 接口幂等拦截器（ex06，纯 Java）→ 多级缓存分层与失效广播（ex07，Caffeine + 模拟 Redis）。验证环境：**OpenJDK 17.0.18（Homebrew）+ Maven 3.9 + Spring Boot 3.3.0**（依赖管理基线，与 ph14~ph17 同源）。

## 验证状态（重要，如实标注）

**本环境无 docker、无 Redis、无 mvn**：依赖真 Redis 的 ex01 标注「未在本环境验证」，需按下方命令起 `docker compose` 后实测；`docker-compose.yml` 同样未在本环境验证。**六个无外部服务的示例（ex02~ex07）已在本机实测通过并标注「已验证」**——ex03/ex04/ex05/ex06 为纯 Java 17 单文件，ex02/ex07 额外依赖 Caffeine 3.1.8（jar 在本机离线 Maven 仓库 `/tmp/m2clone` 中，命令见下表与各文件头注释）。请不要假设本仓库替你在有 Redis 的机器上跑过 ex01。

| 目录/文件 | 主题 | 依赖 | 验证状态 |
|------|------|------|---------|
| ex01-spring-data-redis-cache/ | Redis 五种数据结构 + Cache-Aside + SETNX 锁 + Lua 扣库存 | spring-boot-starter-data-redis（Boot 3.3.0 管理） | 未在本环境验证（需本地 Redis） |
| ex02-caffeine-local-cache/ex02-caffeine-local-cache.java | Caffeine：容量/TTL/统计/LoadingCache | Caffeine 3.1.8 | 已验证（OpenJDK 17.0.18 + Caffeine 3.1.8 本机实测 PASS） |
| ex03-cache-three-problems-demo/ex03-cache-three-problems-demo.java | 缓存穿透/击穿/雪崩成因与防护 | 无（纯 Java 17） | 已验证（OpenJDK 17.0.18 本机实测 PASS） |
| ex04-distributed-lock-semantics-demo/ex04-distributed-lock-semantics-demo.java | 分布式锁：SETNX+TTL、value 校验、Lua 释放、看门狗 | 无（纯 Java 17） | 已验证（OpenJDK 17.0.18 本机实测 PASS） |
| ex05-rate-limit-algorithms-demo/ex05-rate-limit-algorithms-demo.java | 限流：固定窗口/滑动日志/滑动计数器/令牌桶/漏桶 | 无（纯 Java 17） | 已验证（OpenJDK 17.0.18 本机实测 PASS） |
| ex06-idempotency-interceptor-demo/ex06-idempotency-interceptor-demo.java | 接口幂等：结果缓存 + in-flight 防重入 + TTL 窗口 | 无（纯 Java 17） | 已验证（OpenJDK 17.0.18 本机实测 PASS） |
| ex07-multilevel-cache-layering/ex07-multilevel-cache-layering.java | L1(Caffeine)→L2(Redis)→DB 分层 + 失效广播 | Caffeine 3.1.8 | 已验证（OpenJDK 17.0.18 + Caffeine 3.1.8 本机实测 PASS） |

## 运行命令

纯 Java 与 Caffeine 示例（已验证），在各自目录下执行：

```bash
# 纯 Java 示例（ex03/ex04/ex05/ex06）：无第三方依赖
javac <文件名>.java
java <对应主类名>        # 主类名见下表/各文件头

# Caffeine 示例（ex02/ex07）：先定义 classpath（离线 Maven 仓库 /tmp/m2clone 已含 caffeine 3.1.8）
M2=/tmp/m2clone
CP=$M2/com/github/ben-manes/caffeine/caffeine/3.1.8/caffeine-3.1.8.jar:$M2/org/checkerframework/checker-qual/3.37.0/checker-qual-3.37.0.jar:$M2/com/google/errorprone/error_prone_annotations/2.21.1/error_prone_annotations-2.21.1.jar
javac -cp "$CP" <文件名>.java
java -cp "$CP:." <对应主类名>
```

| 文件 | 主类名 |
|------|--------|
| ex02-caffeine-local-cache.java | CaffeineLocalCacheDemo |
| ex03-cache-three-problems-demo.java | CacheThreeProblemsDemo |
| ex04-distributed-lock-semantics-demo.java | DistributedLockSemanticsDemo |
| ex05-rate-limit-algorithms-demo.java | RateLimitAlgorithmsDemo |
| ex06-idempotency-interceptor-demo.java | IdempotencyInterceptorDemo |
| ex07-multilevel-cache-layering.java | MultilevelCacheLayeringDemo |

> 主类名与文件名不一致是本仓库示例的既有约定（单一文件 + 非 public 类，参照 ph17 examples）。各文件头注释已写明「javac 编译 + java 运行」的完整命令。

## 需要真实 Redis 的验证（ex01，未在本环境验证）

```bash
# 1. 起 Redis（7-alpine，6379，healthcheck 就绪约 1~3 秒）
docker compose up -d redis
redis-cli -h localhost -p 6379 ping        # PONG 即就绪
# 2. 跑 ex01（有 mvn 的环境；本机无 mvn，联网环境去掉 -o）
mvn -o -Dmaven.repo.local=/tmp/m2clone -f ex01-spring-data-redis-cache/pom.xml spring-boot:run
# 3. 结束清理（会删除 ex01: 前缀的全部演示键）
docker compose down
```

## 示例速览与教学点

### ex01：Redis 数据结构与缓存用法（未在本环境验证）

五种结构的选型现场：String+TTL（缓存）、Hash（对象字段）、List（队列）、Set（去重）、ZSet（排行）各跑一遍；然后两个高并发核心 API——Cache-Aside 读写姿势（`getOrLoad`）与 Lua 脚本（释放锁的 compare-and-del、库存扣减的原子检查+扣减），全部对应主文档 3.1/3.3/3.4。

### ex02：Caffeine 本地缓存（已验证）

容量封顶（`maximumSize` + `recordStats`）、TTL 过期（注入 `ticker` 让过期可测试）、`LoadingCache` 自动加载、stats 命中率观测——回答「本地缓存为什么快、怎么管容量、怎么观测命中」。

### ex03：缓存三兄弟（已验证）

同一个 CacheAside 引擎拨三个开关，用 **DB 访问计数**证明：穿透无防护 50 次请求=50 次 DB 访问、缓存空值后=1 次；击穿 16 线程并发 miss 无防护回源 16 次、单飞后=1 次；雪崩 120 个 key 无抖动同刻过期=单波 120 次回源、TTL 抖动后峰值显著下降。

### ex04：分布式锁语义（已验证）

`LockStorage` 接口逐条对应 SET NX EX / GET / Lua compare-and-del；场景化出演三个经典坑：不设 TTL 的死锁、裸 DEL 误删他人锁（两把锁并存）、业务比锁长要靠看门狗续期。

### ex05：限流算法（已验证）

固定窗口/滑动窗口日志/滑动窗口计数器/令牌桶/漏桶五选一界面一致（`tryAcquire`），各自用虚拟时钟做出确定性断言——固定窗口边界突发、滑动窗口渐进释放、令牌桶限突发+恒定补充、漏桶绝对匀速。

### ex06：接口幂等（已验证）

注解 `@Idempotent` + `@IdempotentId` + 反射拦截：同键重复请求直接返回首次结果（结果缓存）、并发同键只有一个真正执行业务（in-flight 等待）、TTL 过期后可重放（兜底靠数据库唯一约束）。与 ph16 幂等键、ph17 消费端幂等是同构的「先占位后执行」。

### ex07：多级缓存分层（已验证）

Caffeine 当 L1、内存版 SimRedis 当 L2、假 DB 计数当数据源：分层读只让首读到 DB；一处更新后通过「变更订阅」广播，所有实例的 L1 同时作废（真 Redis 里是 pub/sub / keyspace 通知）；L1 短 TTL + L2 长 TTL 分工。

## 端口与清理

Redis `6379`（ex01 用）；其余示例无网络端口。`docker compose down` 停止 Redis；`*.class` 编译产物在各自目录生成，`rm -f *.class` 清理。
