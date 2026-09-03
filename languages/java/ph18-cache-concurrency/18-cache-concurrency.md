# Java 缓存与高并发阶段

> 面向高性能后端：本阶段承接 ph17 的消费链路，把「缓存分层」变成 DB 前的下一道防线——先会用 Redis/Caffeine 做缓存、能解穿透/击穿/雪崩，再掌握分布式锁与限流的语义与实现，最后用秒杀架构把「入口限流到存储保护」的分层防御串成一条链。

## 1. 概述

本阶段是 Java 学习路线从「能扛中间件」到「能扛流量」的一站。roadmap 第 18 节目标：**掌握高性能后端系统设计**。ph16 把服务拆开（微服务）、ph17 给服务接上消息队列与搜索引擎——但拆完、异步完之后，一个立刻出现的瓶颈是：**所有请求最终都要读数据库，而数据库的 QPS 上限远低于缓存**。本阶段的答案就是两条主线：**缓存**（把高频读挡在 DB 之前）与**高并发防护**（限流、分布式锁、幂等、秒杀编排——把瞬时洪峰挡在存储之外）。

ph17 主文档「下一阶段」的预告在这里逐一兑现：**Redis/Caffeine 缓存用法与穿透/击穿/雪崩**（3.1~3.3）、**分布式锁与限流**（3.4/3.5）、**秒杀架构**（3.7）、**连接池与批量优化**（3.8/3.9）；ph17 的「缓存分层是消费链路的下一道防线」正是 3.2 的本地缓存 → Redis → 数据库三级链路；roadmap 第 21 节的车辆数据实时缓存则建立在本阶段缓存能力之上（本阶段只做单机语义与单节点 Redis，不碰车联网整合）。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 缓存选型与用法 | Redis 五种数据结构与 TTL、Caffeine 本地缓存、两级缓存分层（L1→L2→DB）与失效广播 |
| 缓存三大问题 | 穿透 / 击穿 / 雪崩的成因、判别、解法对比与实现（空值缓存、单飞、TTL 抖动、多级） |
| 分布式锁 | 为什么需要、SET NX EX、唯一标识 value、Lua 原子释放、看门狗续期、Redisson 对照 |
| 限流 | 固定窗口 / 滑动窗口 / 令牌桶 / 漏桶算法对比与实现、键控 + 总量、Redis + Lua 分布式限流 |
| 幂等接口 | 接口层幂等的三件事（防重放 / 防并发重入 / 窗口外兜底）与拦截器语义 |
| 秒杀架构 | 从入口限流到存储保护的分层防御、预扣库存、本地标记优化、异步下单衔接 |
| 连接池与批处理 | DB / Redis / HTTP 连接池参数、批量写入与 Pipeline、异步化与读写分离 |

这个阶段只涉及**缓存与高并发防护的设计、语义与单机实现**，**不涉及 Redis/MySQL 的集群部署、分片与运维调优、监控告警、Docker/Kubernetes 部署**（[ph19 DevOps 与部署阶段](../ph19-devops-deploy/19-devops-deploy.md)；本阶段只用单节点 docker Redis 把 API 跑通）、**不涉及 AQS/Netty 等并发与网络编程底层、JVM 调优**（[ph20 高级 Java 阶段](../ph20-advanced-java/20-advanced-java.md)）、**不涉及车联网方向的组合应用**（ph21 车联网 / 智能电动车方向 Java 阶段，roadmap 第 21 节，目录待建；本阶段的车辆状态缓存只在练习层面用商品/车辆兜底）、**不涉及网关治理框架的接入**（Sentinel/Resilience4j 的规则配置与服务治理属于 ph16 微服务阶段，这里讲的是算法与分布式语义本身）、**不重复 ph17 的 MQ 可靠性细节**（本阶段只在秒杀异步下单处引用其结论：削峰已由 MQ 扛，缓存与限流是再下一层）、**不重复 ph09 的线程池与 AQS 基础**（本阶段直接使用其结论）与 ph13 的 Redis 基础入门（本阶段默认你会 `redis-cli` 与基本数据类型）。

## 2. 来源与演变

缓存的谱系比互联网还老——**缓存就是「把最近最可能再用的结果放近一点」**。1999 年 Java 标准库就内置 `HashMap`（进程内缓存的原型）；2003 年 Brad Fitzpatrick 写 **memcached**，把缓存从「进程内」推向「分布式共享」——多台 Web 服务器共用一批内存节点，解决了进程内缓存各自为政的一致性难题；但它只存内存、无数据结构、挂了即丢。2009 年 Salvatore Sanfilippo 发布 **Redis**（Remote Dictionary Server）——**设计哲学一句话加粗：缓存不只是「键值堆」，而是「带数据结构的服务端内存」**——在 memcached 的 KV 之外给了 String/Hash/List/Set/ZSet 五大数据结构、持久化与丰富命令，单线程模型换来命令天然原子，Lua 脚本（2.6，2012）又让它能执行一段原子的复杂逻辑（限流、扣库存、锁释放的地基）。2014 年 Ben Manes 发布 **Caffeine**（Guava Cache 的作者之一后来也参与其中），用 Window TinyLFU 淘汰算法把进程内缓存做到「接近理论最优命中率」。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| memcached 发布 | 2003 | 分布式内存 KV，Web 缓存事实标准；无数据结构、无持久化 |
| Redis 首发 | 2009 | 数据结构服务器（五种类型 + TTL），单线程命令原子 |
| Redis 2.6 | 2012 | Lua 脚本：服务端原子执行多步逻辑（限流/扣库存/锁释放） |
| Redis 3.0 | 2015 | Cluster 集群、哨兵成熟——集群运维属 ph19，本阶段只用单节点 |
| Guava Cache | 2012 | JVM 内缓存的 Java 事实标准（LoadingCache、LRU 近似） |
| Caffeine | 2014 | Guava Cache 的继任者：Window TinyLFU 淘汰、异步加载、recordStats |
| Redis 6.0 | 2020 | 引入 IO 多线程（命令执行仍单线程）；ACL、客户端缓存等 |
| Redisson | 2014 起 | 用 Redis 实现分布式锁/限流/队列的 Java 库：看门狗续期、红锁 |

两个与高并发直接相关的「协议层演进」值得单列：**分布式锁**从社区自发用 `SETNX`（2009 前后）起家，踩过「没超时 → 死锁」「裸 DEL → 误删他人锁」两个大坑后，2016 年 Redis 官方给出 `SET key value NX EX` 原子拿锁 + Lua 原子释放的标准姿势，Antirez 同年提出 **Redlock**（多节点 quorum 拿锁，争议不断、工程少用——主从切换窗口下仍有双锁风险，见 4.4）；Java 侧 **Redisson**（2014 开源）把「拿锁 + 看门狗续期 + Lua 释放」封装成一行 API。**限流**的算法谱系：令牌桶思想源自 1980 年代的网络流量整形（token bucket，RFC 里给网卡限速的算法），2012 年 Guava 把它带进 Java 应用层（`RateLimiter`，平滑突发/平滑预热），2018 年阿里开源 **Sentinel** 把「滑动窗口计数 + 匀速排队 + 熔断」做成分布式服务治理标准（接入属 ph16，算法本阶段 3.5 讲透）。

> 本阶段只用 Redis 单节点 + 官方客户端做「语义与协议」，**集群部署、分片规划与运维调优属 [ph19 DevOps 与部署阶段](../ph19-devops-deploy/19-devops-deploy.md)**，这里只需在 docker 容器里把 API 跑通。

本文示例以 **OpenJDK 17 + Maven 3.9 + Spring Boot 3.3.0 + Spring Data Redis（Lettuce）+ Caffeine 3.1.8 + Redis 7.x（docker 单节点）** 为基线（选择理由：与 ph14~ph17 完全同基线，Boot 3.3 依赖管理自带 Redis/Caffeine 版本；Caffeine 3.1.8 与 Redisson 3.27.2 在仓库离线 Maven 缓存 `/tmp/m2clone` 中可见）。**本环境无 docker、无 Redis、无 mvn**：依赖真 Redis 的代码（examples/ex01 及全部 Lua/Spring Data 片段）一律标注「未在本环境验证」，需要时用 `docker compose up -d redis` 起服务后按各 README 命令实测；**六个不依赖外部服务的示例（examples/ex02~ex07）已在 OpenJDK 17.0.18 本机实测通过并标注「已验证」**（ex02/ex07 需 Caffeine 3.1.8 离线 jar，classpath 见 examples/README）。缓存与并发的「分层防御心智」多年未变——变的只是组件名与版本号，不变的是「缓存挡读、限流挡洪峰、锁挡并发写、幂等挡重放、最终一致靠 TTL 与对账」。

## 3. 语法与参数

### 3.1 Redis 数据结构与缓存用法

先钉死选型表——五种结构各管一类问题，选型错误是缓存代码最常见的病根：

| 结构 | 适合 | 别用它干 | 命令示例 |
|------|------|---------|---------|
| String | 简单值、计数、分布式锁载体、TTL 缓存 | 存复杂对象字段（改一个字段要整串读写） | `SET/GET/EXPIRE/SETNX/INCR/DECRBY` |
| Hash | 一个对象的多个字段（车辆状态、用户资料） | 需要范围查询/排序 | `HSET/HGET/HGETALL` |
| List | 简单队列/栈（阻塞版 `BLPOP` 可做轻量 MQ） | 需要可靠投递与消费组（那是 ph17 MQ 的事） | `RPUSH/LPOP` |
| Set | 去重、标签、随机抽奖 | 需要有序/带分数 | `SADD/SISMEMBER/SRANDMEMBER` |
| ZSet | 排行榜、延迟队列（score=时间戳）、限流窗口 | 对象主体存储（它只该当索引） | `ZADD/ZREVRANGE/ZRANGEBYSCORE` |

Java 侧的标准姿势是 **Spring Data Redis**（Boot 管理坐标 `spring-boot-starter-data-redis`，默认 Lettuce 连接池，见 examples/ex01）：

```java
// examples/ex01-spring-data-redis-cache/.../Ex01Application.java 摘录 —— Redis 五种结构用法（未在本环境验证，需本地 Redis）
redis.opsForValue().set("ex01:user:1:name", "alice", Duration.ofSeconds(60)); // String + TTL = 最小缓存
redis.opsForHash().put("ex01:vehicle:sn001", "status", "ONLINE");             // Hash：对象字段
redis.opsForList().rightPush("ex01:queue:task", "t1");                        // List：右侧入队
redis.opsForSet().add("ex01:dedup:order-1001", "consumer-a");                 // Set：去重
redis.opsForZSet().add("ex01:rank", "sn001", 88);                             // ZSet：带分数排行
```

**缓存读写姿势（Cache-Aside）**是比任何数据类型都重要的一课——读路径「先查缓存，miss 回源并写回」、写路径「先写 DB，再删缓存」：

```text
读：请求 → 查缓存 ──命中──▶ 返回
                  └─miss─▶ 查 DB ──▶ 写回缓存(带 TTL) ──▶ 返回
写：写 DB ──▶ 删缓存（而不是改缓存）   ← Cache-Aside 的唯一正确姿势，理由见 4.2
```

为什么「删缓存」而不是「改缓存」？改缓存要处理两个并发写把旧值写回的竞态，删缓存则让下一次读自然 miss、回源拿到新值——**删比改多一次读 miss 的代价，但少一整类不一致 bug**。Redis 键命名用 `业务:域:标识`（如 `ex01:user:1:name`）便于按前缀清理与排查。

> 本阶段只用 Spring Data Redis 的同步 API 与命令原语；**ReactiveRedisTemplate / Lettuce 异步客户端属 [ph20 高级 Java 阶段](../ph20-advanced-java/20-advanced-java.md)的高性能 IO 话题**，这里只需理解「Redis 客户端连接池怎么配」（3.8）。

### 3.2 Caffeine 本地缓存与多级分层

**本地缓存（Caffeine）与远程缓存（Redis）是互补关系**：Caffeine 住在 JVM 堆内，读写是内存操作（微秒级、零网络），但它「每实例一份、不跨进程共享」；Redis 跨实例共享但每次读写都有一次网络 RTT（约 0.1~1ms）。所以高并发读的黄金组合是**两级：L1 本地缓存挡掉绝大多数请求，L2 Redis 兜住跨实例共享的数据，DB 只在两级都 miss 时被访问**。

| 维度 | Caffeine（L1 本地） | Redis（L2 远程） |
|------|--------------------|-----------------|
| 延迟 | 纳秒~微秒（进程内存） | 亚毫秒~毫秒（网络 RTT） |
| 容量 | 受 JVM 堆限制 | 独立内存，可远大于单机堆 |
| 共享 | 每实例一份，不共享 | 跨实例共享（集群部署的一致基础） |
| 一致性 | 更新要靠失效广播（3.2/ex07） | 本身是共享真相源 |
| 典型 TTL | 短（秒级，保新鲜） | 长（分钟级，兜底） |

Caffeine 的核心构建参数（examples/ex02 已验证，OpenJDK 17 + Caffeine 3.1.8）：

```java
// examples/ex02-caffeine-local-cache/ex02-caffeine-local-cache.java 摘录 —— 构建一个带 TTL/容量/统计的缓存（已验证）
Cache<String, String> cache = Caffeine.newBuilder()
        .maximumSize(10_000)                        // 容量上限：超限按 Window TinyLFU 淘汰
        .expireAfterWrite(Duration.ofSeconds(30))   // 写后 TTL：最简单、最常见的失效策略
        .removalListener((k, v, cause) -> { /* cause=SIZE/EXPIRED/REPLACED 可分别处理 */ })
        .recordStats()                              // 命中率/驱逐数可观测（上线监控的原料）
        .build();
String v = cache.getIfPresent("session:1");         // 手动读；miss 返回 null
```

**两级缓存的一致性**是整个分层设计最难的部分：L1 是「每实例一份」，实例 A 更新数据后，实例 B 的 L1 里还是旧值。工程套路（examples/ex07 已验证，模拟 Redis 订阅广播）：**更新路径 = 写 DB → 删 L2 → 广播失效**，各实例订阅到变更后清掉自己 L1 的旧值；真 Redis 里广播是 pub/sub 或 keyspace 通知，广播丢失的最后兜底是 L1 的短 TTL（旧数据最多活一个 TTL）。

两级缓存的一组常见参数组合（起步值，压测后按命中率与一致性要求调）：

| 参数 | L1（Caffeine） | L2（Redis） | 理由 |
|------|---------------|-------------|------|
| TTL | 30s~5min | 10min~1h | 本地层离数据近，宁可短保新鲜 |
| 容量 | 数千~数十万条目 | 不限（内存监控） | 本地容量受堆限制，超限靠淘汰 |
| 失效 | 广播收到即 invalidate + TTL 兜底 | 删除为主，不主动改 | 见 4.2「删除利用 miss 即回源」 |
| 粒度 | 业务键（商品 id、配置 key） | 同左 | 两级同键名，广播才能对上 |

> 本阶段默认单节点、单 Redis；**L1 的失效广播、多实例一致性在 4.2 用 CPU 缓存一致性视角讲透**，集群形态（Redis Cluster/哨兵）仍属 [ph19 DevOps 与部署阶段](../ph19-devops-deploy/19-devops-deploy.md)。

### 3.3 缓存三大问题：穿透、击穿、雪崩

三个问题都发生在「缓存 miss 后打到 DB」这条路上，但成因、危害与解法完全不同——先背对比表：

| 问题 | 现象 | 成因 | 危害特征 | 解法 |
|------|------|------|---------|------|
| 穿透 | 每次请求都穿透缓存直达 DB | 查的数据 **DB 里根本不存在**，缓存存不下 | 恶意刷不存在的 id，DB 被空查询打垮 | ① 缓存空值（TTL 短）② 布隆过滤器（缓存前置）③ 参数校验拦截非法 id |
| 击穿 | 一个热点 key 过期瞬间被并发打穿 | 单个**热点 key** 在过期重建的瞬间没有缓存可挡 | 一次重建= N 个并发同时回源，热点拖垮 DB | ① 单飞/互斥重建（并发 miss 只回源一次）② 逻辑过期（读旧值 + 异步重建） |
| 雪崩 | 一大批 key 同时过期/宕机，DB 瞬时被灌满 | 大量 key **同一时刻集体过期**（或 Redis 宕机） | 单波洪峰直接打到 DB 与下游 | ① TTL 加随机抖动 ② 多级缓存（L1 还在）③ 限流兜底 + 熔断降级 |

**穿透的正确姿势是组合拳**：参数校验挡掉明显非法（负数 id）；对「合法但不存在」的 key 缓存空值，空值 TTL 要比正常值短（如 60s vs 10min）——否则正常数据写入后你要等空值过期才能读到（**空值假过期**问题）；更高流量场景在缓存与 DB 之间加**布隆过滤器**，把「集合里没有的 key」在内存里就滤掉（布隆的代价是可能有误判，但不会漏判——误判只会多打一次 DB，可接受）。

| 维度 | 空值缓存 | 布隆过滤器 |
|------|---------|-----------|
| 原理 | 把 null 也当值缓存（短 TTL） | 集合的位图摘要，内存判「不在」 |
| 内存 | O(不存在的 key 数) | O(容量 × 位/哈希)，与 key 数解耦 |
| 误判 | 无（就是缓存了一个 null） | 有（可能把一个存在的判成不存在 → 多打 DB） |
| 清空代价 | TTL 到期自清 | 数据删除后位图不能删单个 key（要重建） |
| 何时用 | 不存在量不大（万级以下） | 不存在量极大且命中 DB 代价高（恶意刷 id） |

**热点 key 的识别与保护**（roadmap 必会概念「热点 key 需要保护」，exercises/sol-01 的热点识别即其入口）：识别靠访问计数（滑动窗口内次数超阈值即标记）；识别后的保护手段按层级排——**预加载/预热**（秒杀前把热点商品塞进缓存，冷启动不裸奔）、**单飞**（过期瞬间不击穿，见下）、**本地短 TTL 副本**（热点数据在每个实例放一份超短 TTL 副本，减少打 Redis 的次数；一致性靠 TTL 与广播）、**本地标记快速失败**（售罄/禁用类状态本地记一份，见 3.7）。

**击穿的单飞是必会实现**（examples/ex03 已验证，纯 Java 16 线程并发断言）：对同一个 key，让并发 miss 的请求**只有一个去回源，其余等结果**。Java 的最小实现是 per-key monitor + 双检：

```java
// examples/ex03-cache-three-problems-demo/... 摘录 —— 单飞（single-flight）核心（已验证：OpenJDK 17 实测）
Object monitor = monitors.computeIfAbsent(key, k -> new Object());
synchronized (monitor) {
    Entry e = map.get(key);
    if (e != null && e.expiresAt > now) return e.value;   // 双检：等待期间别人已回填
    String v = source.load(key);                          // 只有拿到 monitor 的线程真正回源
    map.put(key, new Entry(v, now + ttl));
    monitors.remove(key);                                  // 必须在回填后移除，防止双检失效
    return v;
}
```

**逻辑过期**是单飞的优化：值里带一个「逻辑过期时间」，请求读到「逻辑过期」的值先返回（读旧值），同时异步触发重建——读路径零等待，但牺牲的是短时间的一致（读到的可能是旧值）。最小实现是「缓存的值里放两个字段：真实数据 + 逻辑过期时刻」：

```java
// 逻辑过期的最小形状：命中但逻辑过期 → 先返回旧值，再异步重建（重建并发控 = 单飞，见上）
record LogicalValue<T>(T data, long logicalExpireAt) {}
LogicalValue<Item> hit = cache.getIfPresent(key);
if (hit != null && hit.logicalExpireAt() > clock.now()) {
    return hit.data();                                  // 未逻辑过期：直接读
}
if (hit != null) {
    executor.submit(() -> rebuild(key));                // 逻辑过期：先返回旧值，后台异步重建
    return hit.data();
}
return rebuild(key);                                    // 完全没缓存：只能同步回源（单飞保护）
```

**雪崩的 TTL 抖动**一行就能实现：写入时 `ttl + ThreadLocalRandom.nextInt(300)`，把同一时刻的集体过期摊开成 300ms 内的渐进过期——examples/ex03 场景 C 用虚拟时钟断言：无抖动 120 个 key 单波全过期，加 [0,400ms) 抖动后任意 50ms 窗口的回源峰值显著下降。三兄弟还会**叠加**：穿透的 key 一旦变热就是击穿，多个热点同时过期就是雪崩——所以防御要分层做，别只防一个。

### 3.4 分布式锁：超时与唯一标识

**什么时候需要分布式锁**：单机并发用 `synchronized`/`ReentrantLock`（ph09）就够了——锁对象在同一个 JVM 里；一旦服务多实例部署（ph16），两个 JVM 各自持有一把本地锁，A 实例扣库存时 B 实例也在扣，**临界区必须跨进程互斥**，于是需要一个大家都认的「仲裁者」——Redis（或数据库、ZooKeeper）。分布式锁的全部难点是三个「必须」：

| 必须 | 反例（错误代码） | 后果 |
|------|-----------------|------|
| 拿锁必须带超时 | `SETNX key 1` 不加 EX | 持锁方崩溃 → 锁永不释放（分布式死锁） |
| 释放必须校验唯一标识 | finally 里 `DEL key` | A 的锁超时被 B 顶上后，A 把 B 的锁删了 → 两把锁并存，临界区并发 |
| 释放必须是原子的 | `if GET(key)==myId` 与 `DEL key` 分两步 | 校验与删除之间被插队，等于没校验 |

标准姿势（Redis 原语 + Java 最小实现见 examples/ex04 已验证，场景化出演三个坑）：

```bash
# 以下为 Redis 原语写法，需真 Redis 执行 —— 未在本环境验证（本机无 docker/Redis，见第 2 章验证纪律）
# 拿锁：SET 一条命令带 NX（不存在才写）+ EX（过期时间）——原子，别再 SETNX 后单独 EXPIRE
SET seckill:sku1:lock <uuid> NX EX 30000
# 释放：Lua 保证「校验 value + 删除」原子（value 是拿锁时的唯一标识）
if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end
```

```java
// examples/ex04-distributed-lock-semantics-demo/... 摘录 —— 释放锁必须带 token（已验证：OpenJDK 17 实测）
boolean releaseOk = storage.compareAndDelete(key, token); // ≈ Lua：GET==token 才 DEL
// 若返回 false：锁要么已过期、要么已是别人的 —— 绝不能当成「释放成功」继续
```

**业务比锁长怎么办**：锁有 TTL，但业务（如一次慢查询+远程调用）可能超过 TTL——锁在业务完成前到期，另一个线程就能进来。两个解法：① **看门狗续期**——持锁线程周期性（如每 1/3 TTL）用 Lua「校验自己是持有者就续期」，Redisson 默认开看门狗（锁默认 30s，每 10s 续一次）；② 给业务设超时兜底。注意：看门狗只解决「持锁方还活着但业务慢」，持锁方崩溃时 TTL 依然兜底释放——**锁永远不会永久死锁**。

**Redisson 用法**（本阶段只认 API 形态，需真 Redis，未在本环境验证）：

```java
RLock lock = redisson.getLock("seckill:sku1:lock");
lock.lock(30, TimeUnit.SECONDS);   // 不传 leaseTime 则默认开看门狗自动续期
try { /* 临界区：检查库存 → 扣减 */ }
finally { lock.unlock(); }
```

**可重入与公平**：Redis 锁原生不可重入（同线程再 SET NX 会失败），Redisson 的锁用 Hash 结构（`key -> {token: 重入计数}`）实现可重入；多数业务场景锁的临界区很小、不需要可重入，需要时优先用 Redisson 而非手写 Hash 计数（手写很容易在释放逻辑上引入 bug）。

**锁的粒度是性能与安全的第一取舍**：锁越粗（全局一把锁）越安全但把所有请求串行化，锁越细（每订单/每用户一把）越并发但保护不住跨 key 的不变量。秒杀的正确粒度是 **per-sku（每个商品一把锁）**——不同商品的抢购互不阻塞，同一商品的扣减被串行；而「账号资产变更」这类涉及多个 key 的强一致场景就不该用 Redis 锁（回数据库事务）。判断：**临界区改动的共享状态集合 = 锁 key 的最小边界**。

**Redlock 的红锁争议一句话带过**：主从切换的瞬间，旧主上未同步的锁会在新主上「丢失」，两个客户端可能同时持锁——Redlock 用多数派节点缓解，但分区/时钟问题仍在；工程上多数业务用单 Redis + 看门狗 + 对账兜底（真需要强一致就上数据库/etcd 的分布式事务，那是 ph16 的话题）。

### 3.5 限流：算法与实现

**限流解决的问题**：把进入系统的请求速率压到系统能承受的水位以下，防止流量尖峰打垮下游。四种算法要能说出取舍（examples/ex05 已验证，五种限流器 + 虚拟时钟断言）：

| 算法 | 机制 | 优点 | 缺点 | 场景 |
|------|------|------|------|------|
| 固定窗口 | 每 N 秒一个窗口，窗口内计数 | 最省内存（一个计数） | **窗口边界可瞬时放行 2× 配额**（ex05 场景一演示） | 对边界突发不敏感的粗粒度限流 |
| 滑动窗口日志 | 记录窗口内每个请求的时间戳 | 精确、无边界突发 | 内存 O(窗口内请求数) | 精确优先的小规模场景 |
| 滑动窗口计数器 | 只记相邻两窗计数，按滑出比例加权 | 精度接近滑动窗口、内存固定 | 是近似（±一个请求的偏差） | Sentinel 默认的实现 |
| 令牌桶 | 容量限突发 + 恒定速率补充 | 允许突发、平滑速率，业界最常用 | 需要维护令牌状态 | 接口/用户限流（Guava RateLimiter 系） |
| 漏桶 | 有界队列 + 恒定出桶速率 | 绝对匀速，对下游最友好 | 不允许突发（即使上游有空闲） | 保护下游脆弱系统（如对第三方 API） |

令牌桶实现是面试高频手写题，几十行就能写出正确的（examples/ex05 的 TokenBucket，**先按时间补令牌再取，synchronized 保证并发**）：

```java
synchronized boolean tryAcquire() {
    long now = clock.now();
    tokens = Math.min(capacity, tokens + (now - lastRefill) * tokensPerMs); // 补令牌：只补到桶满
    lastRefill = now;
    if (tokens < 1.0) return false;
    tokens -= 1.0;
    return true;
}
```

**键控 + 总量**是接口限流的正确形态（exercises/sol-02 已验证）：键控给每个用户/接口独立配额（A 刷爆不影响 B），总量兜一层（攻击者**换 key 也能被总量挡住**）——只做键控会被「每次换一个 key」绕过，只做总量会被「一个用户独占全部配额」饿死其他用户。

**分布式限流**：单机版计数在 JVM 里，多实例要搬进 Redis。固定窗口最简版用 `INCR + EXPIRE`，要原子 + 正确需 Lua（未在本环境验证，需真 Redis）：

```lua
-- 分布式固定窗口限流：key = 窗口起始时间，INCR 后判断是否超限（EXPIRE 保证窗口自清理）
local key   = KEYS[1]
local limit = tonumber(ARGV[1])
local count = redis.call('INCR', key)
if count == 1 then redis.call('EXPIRE', key, ARGV[2]) end   -- 首次创建时设窗口过期
if count > limit then return 0 else return 1 end
```

滑动窗口的分布式版用 ZSet（score=时间戳，`ZREMRANGEBYSCORE` 清旧 + `ZCARD` 计数）语义最精确，但每条请求写一个 member、内存与写放大明显——**固定窗口 INCR 是分布式限流的性价比默认**，精度要求高才上 ZSet 或 Lua 令牌桶。

三个概念别混：**限流**（拒绝超额请求，保护上游系统容量）、**熔断**（下游故障时快速失败，不无限等待）、**降级**（故障时返回兜底结果而非报错）。Sentinel/Resilience4j 把三者做成一个规则配置系统（ph16 已讲接入），本阶段讲的是它们底层的算法（限流 = 本节，熔断 = 计数/半开状态机，降级 = 业务兜底设计）。

### 3.6 幂等接口：结果缓存 + 防并发重入

幂等键的思想 ph16 已讲（请求头 `Idempotency-Key`）、ph17 已落到消费端去重表——本阶段补上**接口层拦截器的实现语义**（examples/ex06 已验证）。接口幂等要解决三件事：

| 要解决 | 场景 | 手段 |
|--------|------|------|
| 防重放 | 同一请求重发（客户端重试、网络重发） | TTL 窗口内同业务键不再执行业务，**直接返回首次结果**（结果缓存） |
| 防并发重入 | 两个相同请求同时到达 | in-flight 标记：只有 1 个真正执行，另一个**等结果**（不是也去执行） |
| 窗口外兜底 | TTL 过期后的「很晚的重放」 | 接口层管不住——靠数据库唯一约束 / 状态机（3.7 与练习 3） |

实现骨架（注解 + 反射算业务键，与 examples/ex06 同语义）：

```java
@Idempotent(ttlSeconds = 600)
public String pay(@IdempotentId String orderId, String userId, int amount) { /* 真正写库 */ }
// 拦截器逻辑：按键查「结果缓存」→ 命中直接返回；in-flight 中则等待；否则执行业务并存结果+设 TTL
```

**三处幂等是同构的**：请求层的幂等键、消息层的去重表、接口层的结果缓存，本质都是「**先占位后执行**，占位成功才干活，重复请求返回占位结果」——区别只是占位的载体（Redis/DB/内存）与窗口（TTL/永久唯一键）。

幂等设计最常见的三个错误：① **只做「返回成功」不做「结果一致」**——幂等要求重复请求返回与首次一致的结果（所以要缓存结果，而不是只挡掉重放）；② **把幂等键设计成「会变」**——用时间戳、随机串当键，同一业务每次键都不同，幂等形同虚设；③ **只信接口层、不设 DB 唯一约束**——TTL 窗口外的重放、以及绕过接口的直接调用，只有唯一索引/状态机能兜住（练习 3 就是它的库存版）。

### 3.7 秒杀架构：分层防御的集大成

秒杀是「缓存 + 限流 + 幂等 + 锁 + 库存」的组合应用题，也是本阶段 project 的主题。一次秒杀请求从进来到扣完库存，要过五道闸（每道闸挡一种攻击）：

```text
用户点击 ──▶ ① 入口限流（每用户令牌桶）    挡：脚本点击风暴（一人狂点几万次）
          ──▶ ② 幂等占位（user+sku 唯一）   挡：重复下单、重复扣库存
          ──▶ ③ 商品信息两级缓存            挡：DB（预热后秒杀期间 DB 只该被读几次）
          ──▶ ④ per-sku 分布式锁            挡：多实例并发扣减（临界区串行化）
          ──▶ ⑤ 原子扣库存（CAS/Lua）       挡：超卖（库存永不为负）
          ──▶ 订单记账 + 账实相符
```

| 环节 | 关键点 | 常见错误 |
|------|--------|---------|
| 入口限流 | 每用户配额 + 总量兜底；限流要放在最前面（网关/最外层） | 限流放太深，DB 已先被打了 |
| 商品缓存 | 预热商品信息；**库存不要长期缓存在本地**（一致性难） | 把库存扣减也放本地缓存 → 多实例不一致 |
| 幂等 | user+sku 唯一；下单与扣库存同事务/同锁 | 先扣库存后校验重复 → 重复扣 |
| 分布式锁 | 锁 key 用 skuId；临界区只放「检查+扣减」，越短越好 | 把下单/通知也放进锁 → 锁变成性能瓶颈 |
| 原子扣减 | 锁内再 CAS/Lua 扣一遍（双重保险） | 只靠锁不靠原子扣减 → 锁实现有 bug 就超卖 |
| 兜底 | 库存为 0 后的快速失败（本地标记）、对账任务 | 把「抢不到」当异常处理而不是预期分支 |

**本地标记优化**（3.7 里最常用的性能招）：秒杀开抢后库存从 Redis 扣，但每个请求都要走一次 Redis；当库存为 0 时，让**每个实例本地记一个 sold-out 标记**，之后的请求在本地直接拒绝（返回已售罄），不再打 Redis——库存只在扣减端维护，本地标记只是「读缓存」，代价是标记更新有秒级延迟（可接受，售罄状态不会回退）。

**Redis 预扣的正确姿势**：库存放 Redis（`DECRBY` 前判断够不够），扣减用 Lua 保证「检查 + 扣减」原子（examples/ex01 第 8 步；单机语义版见 exercises/sol-03 的 CAS 与 project/ 的锁内扣减）：

```lua
-- 预扣 1 件：够才扣，返回 1；不够返回 0（原子，Redis 单线程执行，见 4.1）
-- 本 Lua 片段需真 Redis —— 未在本环境验证（完整可运行版见 examples/ex01，依赖 docker 起的 Redis）
local stock = tonumber(redis.call('GET', KEYS[1]) or '0')
if stock >= tonumber(ARGV[1]) then
  redis.call('DECRBY', KEYS[1], ARGV[1])
  return 1
end
return 0
```

**预扣 ≠ 下单**：Redis 扣的库存是「抢到的资格」，数据库订单是「最终事实」——两个状态靠**对账**收敛：定期扫「已扣未落单」的预扣记录，补落单或回补库存。预扣与落单的时序模型有三种，取舍要看对一致性损失的容忍度：

| 模型 | 流程 | 风险/代价 | 场景 |
|------|------|----------|------|
| 同步预扣 + 同步落单 | 锁内扣 Redis → 同一事务写订单 | 请求慢（订单写库在链路里） | 库存小、链路短 |
| 同步预扣 + 异步落单（主流） | 锁内扣 Redis 返回抢到 → MQ 异步写订单 | 预扣成功但落单可能失败 → 靠对账回补 | 高 QPS 秒杀（ph17 MQ 削峰在此落点） |
| 只靠 DB 扣 | 直接事务里 `UPDATE ... WHERE stock>=1` 扣 | 吞吐受 DB 限制 | 流量可控、一致性优先 |

**异步下单**：真正下单（写订单表、扣优惠券、通知）耗时且要写多个系统，同步做完会拖垮秒杀接口——所以秒杀常拆成「**同步预扣**（在锁内快速扣 Redis 库存，返回抢到）+ **异步落单**（发消息给 MQ，消费者写订单表）」。这一步衔接 ph17：**削峰由 MQ 扛住**，而本阶段的缓存与锁保证「预扣阶段」不被打穿。

> 秒杀做完只是高并发架构的开始：**它的姊妹题「多级缓存一致性」「最终对账」在本阶段 4.2 与 5 章收尾**，真实集群的压测与容量规划属 [ph19 DevOps 与部署阶段](../ph19-devops-deploy/19-devops-deploy.md)。

### 3.8 连接池优化：把「每次都用新连接」改掉

高并发系统里连接是稀缺资源（TCP 握手 + 认证很贵），连接池把「创建/销毁」变成「借/还」。Java 后端要管三张池，参数心智各不相同：

| 池 | 常见实现 | 关键参数 | 本阶段建议 |
|------|---------|---------|-----------|
| 数据库连接池 | HikariCP（Boot 默认） | `maximum-pool-size`、`minimum-idle`、`connection-timeout`、`max-lifetime` | 上限别拍脑袋：`((core×2)+spindisk_effective) `启发式起步，看 P99 与等待曲线调 |
| Redis 连接池 | Lettuce（Boot 默认，自带连接复用）/ Jedis | `max-total`、`max-idle`、`min-idle` | Lettuce 默认基于 Netty 共享连接，多数场景无需大池 |
| HTTP 客户端连接池 | `HttpClient` / `RestTemplate` 底下的连接管理器 | `maxConnPerRoute`、`maxConnTotal`、TTL、空闲清理 | 调下游/第三方接口必须有；没有池 = 每次握手 |

三个高频坑：① **池不是越大越好**——DB 连接数超过数据库 `max_connections` 会让连接排队甚至打爆数据库，池大小要配合 DB 侧配置；② **拿连接要设超时**（`connection-timeout`），否则 DB 假死时请求全部堆在池门口等；③ **连接有生命周期**（`max-lifetime` 要小于数据库/中间件的连接回收时间，HikariCP 默认 30min 长于 MySQL 默认 8h 的 `wait_timeout` 是合理方向，反之连接会被服务端悄悄杀掉）。

连接池与线程池是两回事：**线程池管「并发任务数」（ph09），连接池管「并发可用连接数」**——线程池再大，若每个任务都等一个连接，吞吐被连接池卡住；所以调优要「先看等待发生在哪层」（jstack 看线程在等连接还是等任务）。

Boot 下的 HikariCP 配置形态（参数心智见上表；`minimum-idle` 别等于 `maximum-pool-size`，否则闲时也占满连接）：

```yaml
# application.yml —— HikariCP（Boot 默认数据源）起步参数（未在本环境验证，无 DB 服务）
spring:
  datasource:
    hikari:
      maximum-pool-size: 20          # 起步启发式：((core×2)+spindle)；看 DB 侧 max_connections 别超
      minimum-idle: 5
      connection-timeout: 3000       # 拿不到连接快速失败，别让请求无限等池
      max-lifetime: 1800000          # 30min，小于 MySQL wait_timeout(默认8h) 同向；服务端回收前自断
      validation-timeout: 1000
      pool-name: seckill-hikari      # 命名后 jstack/日志好认
```

### 3.9 异步化、批处理与读写分离：把同步链路改薄

高并发最后的三大招是把「每个请求必须同步做完的事」减到最少：

**异步化**：请求链路里可以后置的耗时动作（发通知、写日志、更新统计、触发下游），从同步调用改成「丢给异步执行」。三种载体：① 线程池/`CompletableFuture`（ph09，适合进程内、结果还要等的情况）；② 消息队列（ph17，跨服务削峰解耦的正解）；③ 虚拟线程（Java 21，ph09 预告，把「阻塞即让位」做到极致）。判断标准一句话：**调用方不需要这个结果才能继续 → 就该异步**；否则异步只会把复杂性从请求里挪到状态管理里。

**批处理**（exercises/sol-04 已验证）：同样的写操作，「逐条写 = 往返次数 × 条数」；「攒批写」把一批塞进一次往返（JDBC `addBatch`、数据库批量 INSERT、MQ 批量投递），Redis 侧还有更极致的 **Pipeline**——命令一条不省，但 500 条命令一趟 RTT 送达（sol-04 的对照表：roundTrips 500 → 5 → 1，最终落库状态三者完全一致）。批量优化的代价：一条失败整批重放、批内有延迟窗口（数据不是立即可见）、内存要攒 buffer——取舍着用。Redis 的 `MGET/MSET` 是「读写的批量」天然形态，配合 `pipelined` 能显著压低 RTT 占比。

**读写分离**：主库写、从库读，把读流量从主库分流（本阶段只讲 Java 侧姿势：`@Transactional(readOnly = true)` 路由到从库、ShardingSphere/手动多数据源配置属 ph13/ph16 已讲范围）。铁律：**从库延迟 = 读写不一致窗口**，刚写完立刻读从库可能读不到（`read-your-writes` 问题）——对一致性敏感的数据要么读主、要么接受短暂延迟。读写分离与缓存一样都是「用一致性换吞吐」，能不用就别用，用了就要把「哪些数据能接受延迟」钉死。

进程内异步的 Java 形态（线程池 / CompletableFuture，ph09 已讲 API，这里给链路里的用法）：

```java
// 请求内可后置的动作：发通知 + 记审计不阻塞下单响应（错误各自兜底，别在主线程抛）
CompletableFuture.runAsync(() -> notifyService.push(order), notifyPool)
        .exceptionally(ex -> { log.error("notify failed orderId={}", order.id(), ex); return null; });
CompletableFuture.runAsync(() -> auditService.record(order), auditPool);
return "下单成功"; // 主响应不等待这两个动作
```

异步化分级落地：能异步到消息队列的走 MQ（跨服务，ph17），进程内通知/审计类走线程池（本段），再大的「未来 IO 等待」交给虚拟线程（Java 21，ph09 预告）。

## 4. 底层原理

### 4.1 Redis 单线程模型与 IO 多路复用：为什么「快」而且「原子」

Redis 高性能与原子性的根源是同一个设计：**命令执行是单线程的**。所谓「单线程」指的是「执行命令的线程只有一个」——事件循环里串行处理所有客户端的命令：

```text
客户端连接 ──▶ epoll（IO 多路复用：一个线程盯着成千上万个 socket）──▶ 命令队列
                                                                        │
      响应 ◀── 执行结果 ◀── 单线程逐条执行命令（内存操作，μs 级）◀──────┘
```

- **为什么快**：内存数据结构（HashMap/跳表）读写是微秒级；网络 IO 用 epoll 多路复用，一个线程同时盯所有连接，没有线程切换与锁竞争；6.0 后 IO 读写也可多线程（减少系统调用开销），但**命令执行仍是单线程**。
- **为什么原子**：单线程执行意味着**一条命令永远不会被另一条命令插队**——`INCR` 天然无竞态；需要多步原子逻辑时用 Lua 脚本，脚本整体在事件循环里执行完才处理下一条命令。**这就是「Redis 里做扣库存、拿锁、限流天然安全」的全部秘密**：不是 Redis 有锁，而是它根本没有并发执行。
- **代价与边界**：单线程意味着**单条命令要快**（`KEYS *`、大 `HGETALL` 这种 O(N) 命令会阻塞整个 Redis 到执行完，这就是生产禁用 `KEYS` 的原因）；CPU 密集操作（如复杂 Lua）也吃同一个核。集群扩算力是 ph19 的话题，本阶段记得「命令要快、脚本要短」。

### 4.2 缓存一致性的本质：从 CPU 缓存一致性协议看两级缓存

多级缓存的一致性不是一个 Java 问题，而是**计算机系统结构的老问题**——CPU 早就遇到一模一样的事：L1/L2/L3 缓存与主存之间的数据一致。CPU 的解法是 **MESI 协议**：每个缓存行带状态（Modified/Exclusive/Shared/Invalid），一个核写数据时通过总线广播**使其他核的副本失效（invalidate）**。对照两级业务缓存：

| CPU 缓存 | Java 业务缓存 | 
|---------|--------------|
| 每核私有 L1 | 每实例私有 L1（Caffeine） |
| 共享 L2/L3/主存 | 共享 L2（Redis） |
| 缓存行失效广播（总线嗅探） | pub/sub / keyspace 通知（广播失效） |
| 写回/写穿策略 | Cache-Aside / Write-Through 等 |
| 可见性屏障（内存屏障/fence） | 「先删缓存再放行请求」「删完再广播」的顺序纪律 |

工程结论与 CPU 协议殊途同归：**私有缓存的一致性不靠「私有缓存自己更新」，而靠「失效信号被广播、各核（各实例）收到后把副本作废」**——所以两级缓存的写路径纪律是「**写 DB → 删 L2 → 广播失效**」（examples/ex07 已验证：一处更新，所有实例的 L1 同时作废）。顺序为什么不能乱：如果先删缓存再写 DB，写 DB 失败的窗口里别人读到 DB 旧值却已无缓存（多一次 miss 而已，可接受）；如果先写 DB 再删缓存，删除前的窗口里读到旧缓存——所以要接受「删除前有短暂旧值」，用 TTL 兜底，而不是试图做到绝对零窗口（绝对一致只能回到单写者 + 强一致存储，即放弃多级缓存）。

**Cache-Aside 为什么删缓存不更新缓存**也能从协议视角理解：更新缓存 = 把「主存的新值」写进私有副本，但其他核的副本不会跟进（除非也收到广播）；删除 = 发失效信号，所有副本下次访问自然回源拿新值——**删除利用的是「miss 即回源」这个天然机制，比把新值推给所有副本省心得多**。布隆过滤器、单飞（3.3）在 CPU 世界也有对应物（预测器、请求合并），缓存一致性的心智模型是通用的。

### 4.3 限流令牌桶与漏桶的实现细节

算法的实现正确性藏在三个细节里，面试与生产都在这里翻车（examples/ex05 已验证全套）：

1. **令牌桶必须先补后取**：`tokens = min(capacity, tokens + 流逝时间×速率)` 之后再判断 `tokens >= 1`——先取后补会让长时间闲置后的第一个请求被错误拒绝。
2. **补令牌用「惰性结算」而不是定时任务**：不需要一个后台线程每秒补一次令牌——在每次 `tryAcquire` 时用「距上次补充的时间 × 速率」一次性结算即可（上面的代码就是惰性结算）。定时补充会带来实现复杂性与时钟误差，惰性结算数学上等价。
3. **固定窗口的「边界突发」是数学必然**：窗口 [0,1000) 放满 3 个，[1000,2000) 又能放满 3 个——若两个窗口的请求都在 1ms 内到达，瞬间放行 6 个。滑动窗口日志消除了这一点但要存时间戳，滑动窗口计数器只记两窗计数、用「上一窗口的滑出比例」加权近似——ex05 场景三演示了它在窗口边界「只放行 1 个而不是 3 个」的行为。

漏桶的实现正确性在「**出桶节奏恒定**」：每 `drainMs` 只允许一个请求真正放行，队列里积压的请求按到达顺序排队——所以漏桶天然削峰，但代价是突发请求即使系统当时有空闲也会被匀速化（ex05 场景五：瞬时最多入桶 3 个，之后严格 1 个/秒放行）。**令牌桶 vs 漏桶的取舍本质**：令牌桶「有空闲就允许突发（桶里的令牌代表历史空闲）」，漏桶「不管上游多急，输出恒速」——前者对调用方友好、后者对下游（DB/第三方 API）友好。

### 4.4 数据库锁与分布式锁：谁在背后保证「不超卖」

把「库存扣减」的实现链路看穿，会发现每层锁的保证机制不同：

| 层级 | 机制 | 谁保证互斥 | 崩溃/超时行为 |
|------|------|-----------|--------------|
| 单机 `synchronized`/AQS | JVM 内 Monitor/队列 | JVM 内存模型（ph09） | 持锁线程崩溃锁自动释放（JVM 回收） |
| 数据库悲观锁 `SELECT ... FOR UPDATE` | 数据库行锁 | InnoDB 行锁 + 事务 | 事务回滚释放锁；有死锁检测与超时 |
| 数据库乐观锁 `UPDATE ... SET stock=stock-1 WHERE stock>=1` | 受影响行数判定 | 数据库单行更新的原子性 | 无锁可超时，靠重试；行级串行化由数据库保证 |
| Redis `SET NX EX` 分布式锁 | Redis 单线程命令原子 | Redis 单线程执行模型（4.1） | **超时自动释放**（这是它与 JVM 锁最大的不同） |
| 数据库唯一约束 | `INSERT ... ON CONFLICT` / 唯一索引 | 索引唯一性 | 幂等的最终防线，无锁语义但永不过期 |

理解这张表就能回答「为什么秒杀要把库存扣减放在锁里还要原子扣减」：**分布式锁保证「同时只有一个实例在扣」，原子扣减（CAS/Lua）保证「即使锁实现有 bug（如主从切换丢了锁），单次扣减也不会扣成负数」**——两层不同机制的防御叠加，哪一层单独出问题都不会超卖（锁实现 bug → 多实例并发扣，但 CAS 挡住负库存；CAS 有 bug → 锁保证单写者）。数据库唯一约束则是「订单层」的最终防线：无论上层怎么并发重放，同一个 `user+sku` 只能有一行订单。

**分布式锁与数据库锁的本质差异**：数据库锁的互斥由「存储引擎的行锁」保证，事务结束自动释放，强一致但慢（行锁 + 事务开销）；Redis 锁的互斥由「单线程执行 SETNX」保证，超时自动释放（这是为崩溃设计的），快但弱一致（主从切换、网络分区下可能出现双持锁窗口）。**选型结论**：短临界区、高并发、可容忍「极小概率双持 + 业务幂等兜底」→ Redis 锁；必须强互斥、临界区长、失败要回滚 → 数据库/事务。秒杀用 Redis 锁做「预扣」性能层、数据库事务做「最终落单」正确层——**两层都不省**（project/ 的验收标准就在验证这件事）。

数据库条件更新的正确姿势（乐观锁的 SQL 形态，`WHERE` 把版本/库存条件带进去，返回受影响行数）：

```sql
-- 扣 1 件：行锁 + 条件更新二合一，受影响行数 = 1 才算成功（0 = 库存不足/被别人抢先）
UPDATE seckill_stock SET stock = stock - 1, version = version + 1
WHERE sku_id = ? AND stock >= 1;
```

在 Java 里用 `int rows = jdbcTemplate.update(sql, skuId);` 的返回行数判定成败——这一行是「数据库层不超卖」的全部秘密：**单行 UPDATE 的行锁让并发扣减排队执行，条件 `stock >= 1` 保证扣不成负数，受影响行数把「谁扣到了」显式交给应用**。Redis Lua 预扣（3.7）与它是同一语义在不同载体上的实现。

## 5. 使用场景

- **高并发分层防御（本阶段场景主线）**：一次秒杀/抢购/热点读请求从进来到存储要过「入口限流 → 幂等 → 缓存 → 锁 → 存储保护」五道闸，每道闸的职责与挡的攻击不同（3.7 表）；任何一层单独存在都不够——没有限流，缓存和 DB 会被刷爆；没有幂等，重试会重复扣；没有锁，多实例并发写会错乱。roadmap 必会概念「高并发要从入口限流到存储保护」就是这个意思。
- **什么时候用多级缓存**：读多写少、数据一致性要求不苛刻（可接受秒级延迟）、单条数据价值高（热点）——商品详情、车辆状态、配置、排行榜都是典型；写极频繁或强一致要求（余额、库存的最终判定）**不要**放缓存，缓存只当预扣/预读层，最终以 DB 为准。
- **什么时候不用 Redis 锁**：临界区在一个 JVM 内（用 ph09 的本地锁更快）；需要强互斥且失败要回滚（用数据库事务）；系统只有一个实例且不会扩容（分布式锁是纯开销）。引入分布式锁 = 引入超时权衡与运维依赖——没到多实例就别上。
- **限流放哪一层**：网关/接入层挡「外网流量」（nginx、ph16 网关、Sentinel），业务层按用户/接口做更细的键控限流（3.5），两层各管一段——网关管总量、业务层管公平。
- **批量与异步的适用边界**：写吞吐瓶颈在「往返次数」时先上批量（Pipeline/批量 INSERT，sol-04）；在「单条处理时间」时再谈异步化；调用方不需要结果才异步，否则复杂度会从请求挪进状态管理。读写分离只在读流量显著大于写且可接受从库延迟时上。
- **缓存三大问题的排查口诀**：缓存 miss 打 DB → 先问「DB 有没有这条数据」（没有 = 穿透）、再问「是不是单个 key 被打」（是 = 击穿）、再问「是不是一大批 key 同时过期」（是 = 雪崩）——问题定性才能对症下药，三个解法不能互相替代（3.3）。
- **跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）：缓存与并发的**心智模型（缓存分层、锁语义、限流算法）是语言无关的**，但落地体验差在生态——Java 有 Spring 的 `@Cacheable` 注解抽象（配 Caffeine/Redis 只改依赖与配置）、Redisson 的锁/看门狗封装、Sentinel 的规则配置，把「协议正确性」都吃进了框架；Go 的客户端（go-redis、singleflight 库）更薄，缓存失效广播、看门狗往往要自己拼；C++/Rust 生态则连 JVM 那种「注解即 AOP」的魔法都没有，全靠显式代码。横切点：**「并发协议的正确性」是语言与中间件共有的，而「样板量」由框架生态决定**——Java 靠生态把高并发编程的门槛压到「会选参数、懂语义」。
- **什么时候别用缓存**：数据一秒变好几次且读得不频繁（缓存命中率低，纯浪费）；一致性要求严苛到「缓存与 DB 一个字节都不能差」（这类诉求应该先质疑架构）；数据量小到 DB 本身毫秒内能返回（缓存是徒增复杂度）。**引入缓存的代价 = 一致性管理（3.3/4.2）+ 容量与命中率监控（3.2）**——没这层觉悟不要上缓存。

选型速查（对照 3.1~3.9 各表）：

| 需求 | 首选 | 理由 |
|------|------|------|
| 进程内高频读（最热一层） | Caffeine | 零网络、纳秒级；配合失效广播保一致（ex07） |
| 跨实例共享缓存 / 状态 | Redis | 数据结构 + TTL + Lua 原子性（ex01） |
| 多实例临界区互斥 | Redis 锁（SETNX+Lua+看门狗） | 秒级短临界区的性能与简单（ex04/Redisson） |
| 强互斥 + 事务回滚 | 数据库事务/行锁 | 可靠性优先，性能其次（4.4） |
| 单机接口限流 | 令牌桶（本地实现） | 允许突发 + 平滑（ex05） |
| 多实例分布式限流 | Redis + Lua | 计数全局一致（3.5） |
| 防重放 + 防并发重入 | 幂等键/结果缓存 + DB 唯一约束 | 分层防（ex06/exercises sol-03） |

## 6. 代码示例

> 完整可运行版在 [`examples/`](./examples/)（七个示例 + `docker compose` 起 Redis）。验证环境：OpenJDK 17.0.18 + Maven 3.9 + Spring Boot 3.3.0（依赖管理基线）；**依赖真 Redis 的 ex01 标注「未在本环境验证」**，需先 `docker compose up -d redis`；**ex02~ex07 已在本机实测全部 PASS 并标注「已验证」**（ex02/ex07 额外依赖 Caffeine 3.1.8 离线 jar）。练习参考实现（sol-01~04）在 [`exercises/`](./exercises/)，项目在 [`project/`](./project/)。

```java
// examples/ex05-rate-limit-algorithms-demo/ex05-rate-limit-algorithms-demo.java —— 五种限流算法统一 tryAcquire（已验证：OpenJDK 17 实测）
FixedWindowLimiter fw  = new FixedWindowLimiter(clock, 1_000, 3);
SlidingWindowLogLimiter sw = new SlidingWindowLogLimiter(clock, 1_000, 3);
TokenBucketLimiter tb  = new TokenBucketLimiter(clock, 5, 10);      // 容量 5，每秒补 10
LeakyBucketLimiter lb  = new LeakyBucketLimiter(clock, 3, 1_000);   // 队列 3，每秒出 1
```

```java
// examples/ex04-distributed-lock-semantics-demo/... —— 正确释放锁：compare-and-delete（已验证：OpenJDK 17 实测）
SafeLock a = new SafeLock(storage, clock, "stock:sku1:lock", 1_000);
a.tryLock();                                   // SET key token NX EX 1000
// ... 业务超过 TTL，锁被 B 顶上 ...
boolean ok = a.unlock();                       // Lua GET==token 才 DEL → false，B 的锁安然无恙
```

### 示例 1：Redis 五种结构与 Lua（[`examples/ex01-spring-data-redis-cache/`](./examples/ex01-spring-data-redis-cache/)）

String/Hash/List/Set/ZSet + Cache-Aside + `SETNX` 锁 + Lua 原子扣库存。需本地 Redis（`docker compose up -d redis`），未在本环境验证。

### 示例 2：Caffeine 本地缓存（[`examples/ex02-caffeine-local-cache/ex02-caffeine-local-cache.java`](./examples/ex02-caffeine-local-cache/ex02-caffeine-local-cache.java)）

容量 / TTL / LoadingCache / recordStats 全 API 演示，注入 ticker 让过期可确定性断言（已验证：OpenJDK 17.0.18 + Caffeine 3.1.8）。

### 示例 3：缓存三兄弟（[`examples/ex03-cache-three-problems-demo/ex03-cache-three-problems-demo.java`](./examples/ex03-cache-three-problems-demo/ex03-cache-three-problems-demo.java)）

穿透（空值缓存）、击穿（单飞，16 线程并发断言回源 1 次）、雪崩（TTL 抖动）用同一引擎三个开关对照演示（已验证：OpenJDK 17 实测）。

### 示例 4：分布式锁语义（[`examples/ex04-distributed-lock-semantics-demo/ex04-distributed-lock-semantics-demo.java`](./examples/ex04-distributed-lock-semantics-demo/ex04-distributed-lock-semantics-demo.java)）

不设超时的死锁、裸 DEL 误删他人锁、value+Lua 正确释放、看门狗续期四个场景，每个错误都对应一个 Redis 反例（已验证）。

### 示例 5：限流算法（[`examples/ex05-rate-limit-algorithms-demo/ex05-rate-limit-algorithms-demo.java`](./examples/ex05-rate-limit-algorithms-demo/ex05-rate-limit-algorithms-demo.java)）

固定窗口 / 滑动窗口日志 / 滑动窗口计数器 / 令牌桶 / 漏桶 + 边界突发等陷阱的确定性断言（已验证）。

### 示例 6：接口幂等拦截器（[`examples/ex06-idempotency-interceptor-demo/ex06-idempotency-interceptor-demo.java`](./examples/ex06-idempotency-interceptor-demo/ex06-idempotency-interceptor-demo.java)）

注解 + 反射解析业务键 + 结果缓存 + in-flight 防重入，串行重放与并发重复都只执行一次业务（已验证）。

### 示例 7：多级缓存分层与失效广播（[`examples/ex07-multilevel-cache-layering/ex07-multilevel-cache-layering.java`](./examples/ex07-multilevel-cache-layering/ex07-multilevel-cache-layering.java)）

Caffeine L1 + 模拟 Redis L2 + DB 三级读；更新广播让 A/B 两实例 L1 同时作废；两级 TTL 分工（已验证）。

## 7. 总结

### 关键要点

- **缓存分层是消费链路的下一道防线（ph17 预告兑现）**：L1 本地挡大多数读、L2 Redis 共享兜底、DB 只该被真正回源；TTL 是缓存的最终兜底，缓存一律「先写 DB 再删缓存」
- **三大缓存问题的解法不能互相替代**：穿透靠空值缓存/布隆（防不存在的数据）、击穿靠单飞/互斥重建（防单点热点过期）、雪崩靠 TTL 抖动 + 多级 + 限流（防集体过期）；三兄弟会叠加，防御要分层
- **分布式锁三个必须**：拿锁带 TTL（防死锁）、释放校验唯一标识（防误删他人锁）、校验与删除原子（Lua）；看门狗解决「业务比锁长」，崩溃时 TTL 兜底
- **限流四选一**：固定窗口省内存但有边界突发、滑动窗口日志精确但费内存、滑动窗口计数器是折中、令牌桶允许突发+平滑（最常用）、漏桶绝对匀速（保护下游）；键控 + 总量两层都要，分布式计数搬进 Redis+Lua
- **接口幂等三件事**：结果缓存挡重放、in-flight 挡并发重入、DB 唯一约束兜底窗口外——三处幂等（请求/消息/接口）本质都是「先占位后执行」
- **秒杀是分层防御的集大成**：限流 → 幂等 → 缓存 → per-sku 锁 → CAS 扣减 → 订单，每层挡一种攻击；锁保证「只有一个在扣」，原子扣减保证「扣不成负数」，两层不省
- **连接池与批处理是吞吐的最后一块拼图**：池不是越大越好、拿连接要设超时；批量/Pipeline 把往返从 O(条数) 降到 O(批数)；调用方不需要结果才异步

### 阶段验收清单

- [ ] 能给一个场景说出 Redis 五种数据结构的选型，能写出 Cache-Aside 读写的正确顺序并解释为什么「先写 DB 再删缓存」
- [ ] 能说清 Caffeine 与 Redis 的定位差异（延迟/共享/容量/一致性）与两级缓存的分层结构
- [ ] 能区分穿透/击穿/雪崩并各给出至少两种解法；能写出带双检的单飞重建
- [ ] 能解释分布式锁的 SET NX EX、value 校验与 Lua 释放，说出无 TTL/裸 DEL/业务超锁三种事故的后果
- [ ] 能画出四种限流算法并说出取舍；能实现键控 + 总量的接口限流并说明分布式版怎么落 Redis
- [ ] 能解释接口幂等三件事（防重放/防并发重入/窗口外兜底）与实现形态
- [ ] 能画出秒杀五道闸并说出每层挡什么；能说出锁与原子扣减为什么是两层不省的防御
- [ ] 能说出连接池三类参数的心智；能设计批量写入并说明 Pipeline 为什么快
- [ ] 能解释 Redis 单线程模型为什么带来命令原子性，以及多级缓存一致性为什么靠「失效广播 + TTL 兜底」

### 跨语言对比

- 缓存/锁/限流的**心智模型语言无关**，差异在生态样板量：Java 用 Spring 缓存抽象 + Redisson + Sentinel 把协议吃进框架，Go（go-redis/singleflight）与 C++ 偏薄客户端、语义要自己拼——本阶段的语义练习（examples/ex03~07、sol-01~04、project）正是「把框架吃掉的样板亲手拼一遍」，做完再看 Spring 的 `@Cacheable` 或 Redisson 会一目了然（为 analysis/ 与 Tenet 合成积累素材）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：热点数据缓存（练习 1）→ 接口限流（练习 2）→ 库存扣减（练习 3）→ 批量写入优化（练习 4），四题对应 roadmap 第 18 节列出的四个练习。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**秒杀系统 demo**（roadmap 推荐项目）——把限流、幂等、两级缓存、per-sku 分布式锁、CAS 扣库存按「从入口到存储」的分层防御串成一条链，300 并发抢 30 件库存恰好 30 人成功、无超卖、DB 只回源 1 次，纯 Java 17 无依赖、`javac`/`java` 即可跑通全部验收（已在 OpenJDK 17.0.18 本机验证）。建议完成练习后再动手。
- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`java -cp out seckill.SeckillApp` 全部 PASS）

### 下一阶段

[ph19 DevOps 与部署阶段](../ph19-devops-deploy/19-devops-deploy.md)——本阶段的单节点 Redis 与手压并发要变成生产形态：Docker 镜像打包（ph18 的秒杀 demo 换成 Dockerfile + compose 起 Java + MySQL + Redis）、CI/CD、监控告警（命中率、QPS、连接池水位都要可观测）、集群与容量规划。本阶段埋的前置：秒杀 demo 的「模拟后端换真 Redis」、缓存命中率监控指标、连接池调优参数——都是 ph19 上生产时要接的线；roadmap 第 21 节的车辆状态实时缓存则以本阶段的两级缓存与失效广播为地基。
