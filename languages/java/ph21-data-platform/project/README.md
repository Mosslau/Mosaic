# ph21 阶段项目：数据平台后台平台(source-iot, 收官项目)

> 对应 roadmap §21「推荐项目」第一个「数据平台后台平台」。本平台是 **Java 学习路线的收官项目**：把 ph01~ph20 的机制(并发/CHM/线程池、Netty 接入形态、SPI 规则、DDD 建模、Kafka 消费语义、版本发布 状态机、运维聚合)按真实数据平台数据链路组织成**一个纯 Java 可 javac 编译测试的模块集**。采用 ph18 秒杀 demo 的「纯 Java 可测先例」与 ph19 部署模板结构：模块边界即服务边界，全部内存实现、可离线跑、输出即验收。

## 需求

roadmap §21 示例骨架是 `数据源 → 接入服务 → Kafka → 清洗/告警/存储 → 后台平台`。本项目的模拟链路与它一一对应：

```text
3 个模拟数据源 ─并发─▶ IngestService(校验+去重) ─▶ MetricsBus(按 sourceId 分区≈Kafka)
        ─▶ MetricsConsumer.drain ─▶ 状态缓存 + 作业历史 + 节点在线 + 告警引擎
ReleasePlatform(版本库/批次/回滚/审计) ────────────────────────────┘
                OpsConsole(运维后台聚合) ◀── 各域只读快照
```

模块边界即「微服务切分」的教学切片(每个模块=一个限界上下文，ph20 DDD 落地)：

| project 模块 | 对应真实服务 | 用到的 ph01~ph20 机制 |
|--------------|-------------|----------------------|
| `NodeRegistry` | 节点管理服务 | 聚合根 + 状态机 + CAS 更新(ph02/ph04/ph20 DDD) |
| `MetricsFrame` | 协议层(网关解码后) | record + 量程校验(ph02/ph03) |
| `IngestService` | 接入服务 | 并发去重 + CAS + 计数(ph09/ph20 JMM) |
| `MetricsBus` | Kafka topic | 按 key 分区、append-only、offset(ph17) |
| `MetricsConsumer` | 指标消费服务 | 先处理再 commit、积压 lag(ph17) |
| `SourceStateCache` | Redis 实时状态缓存 | ConcurrentHashMap.compute 原子读改写(ph18/ph20 CHM) |
| `JobHistoryStore` | 作业历史服务 | 每个数据源历史点 + 并发队列(ph04) |
| `AlertEngine`/`AlertRules` | 告警规则引擎 | 规则可插拔(依赖倒置，ph20 SPI 思想) |
| `ReleasePlatform` | 版本发布 管理平台 | 版本语义比较 + 批次状态机 + 审计 + 回滚(ph08/ph20) |
| `OpsConsole` | 运维后台 | 跨域聚合视图(ph08 Stream) |

## 目录结构

```text
project/
├── README.md
└── src/sourceiot/
    ├── SourceIotPlatformDemo.java   # 端到端演示 + 验收断言(14 项 PASS)
    ├── NodeRegistry.java           # 节点注册/状态/固件(数据源档案聚合)
    ├── MetricsFrame.java           # 指标帧 record + 协议解码 + 量程校验
    ├── IngestService.java            # 接入服务：去重/坏帧拦截/投递总线
    ├── MetricsBus.java             # 内存版 Kafka(8 分区，按 sourceId 哈希)
    ├── MetricsConsumer.java        # 消费服务：drain + 更新多下游
    ├── SourceStateCache.java        # 实时状态缓存(CHM.compute 原子更新)
    ├── JobHistoryStore.java               # 作业历史点存储(每个数据源最近 N 点)
    ├── AlertRule.java                # 告警规则接口
    ├── AlertRules.java               # 内置两条规则(LowSoc / Overheat)
    ├── AlertEngine.java              # 规则求值 + 活跃告警表
    ├── ReleaseVersion.java               # 语义化版本号(可比较)
    ├── ReleasePlatform.java              # 版本发布 平台：版本库 + 批次 + 状态机 + 审计
    └── OpsConsole.java               # 运维后台聚合视图
```

## 构建与运行(已验证)

验证环境：**OpenJDK 17.0.18(Homebrew，/opt/homebrew/opt/openjdk@17)**；零第三方依赖。

```bash
# 1. 编译(在 project/ 目录执行，产物输出到 /tmp)
JAVAC=/opt/homebrew/opt/openjdk@17/bin/javac
JAVA=/opt/homebrew/opt/openjdk@17/bin/java
$JAVAC -encoding UTF-8 -d /tmp/tl21-proj src/sourceiot/*.java
# 2. 运行端到端演示(输出即验收报告)
$JAVA -cp /tmp/tl21-proj sourceiot.SourceIotPlatformDemo
# 3. 清理
rm -rf /tmp/tl21-proj
```

运行输出 14 行 `PASS ...`(见下方验收标准)并以 `ALL PASS: 14/14` 结束，另打印运维总览（6 个数据源/在线 3/告警 2/无积压）。

## 功能清单

- [x] 节点管理：注册 6 个数据源、状态迁移(CAS 更新)、固件版本升级落档案
- [x] 数据源接入：3 个模拟数据源并发上报 1200 帧，坏帧拦截(6 条)与重发去重(9 条)计数精确
- [x] 数据总线：按 sourceId 哈希入 8 分区；消费端先处理再推进 offset，drain 后 lag=0
- [x] 实时状态缓存：每个数据源最新帧收敛到 seq=400(乱序/旧帧不会覆盖)
- [x] 作业历史落库：1200 个作业历史点全部入库
- [x] 告警引擎：末帧注入 CPU 水位=8% 与磁盘 135℃ → LOW_CPU 水位 与 DISK_OVERHEAT 各 1 条活跃告警
- [x] 版本发布 平台：版本递进发布(1.4.0→2.0.0→2.2.0)、批次推进、2 成功 1 失败、失败数据源回滚(ROLLED_BACK)、成功数据源版本生效
- [x] 运维后台：跨域聚合读数(数据源/在线/告警/积压)与「每个数据源状态 + 版本发布 进度」明细

## 验收标准

- `java -cp /tmp/tl21-proj sourceiot.SourceIotPlatformDemo` 输出 14 行 PASS 且以 `ALL PASS: 14/14` 结束(本机实测稳定)
- 你能回答三个「为什么」(对照主文档 3.x)：
  1. 为什么 `IngestService` 用「每个数据源 `AtomicLong` + CAS」而非锁就能并发去重？(`computeIfAbsent` + `compareAndSet`，ph20 CHM 语义)
  2. 为什么消费端「处理完一批再推进 offset」，顺序反了会怎样？(先 commit 后处理 = 崩溃即丢数据，ph17)
  3. 为什么 `SourceStateCache.update` 用 `compute` 一段式而非 `get + put`？(两段之间有竞态窗口，ph20 3.6)
- 加一个扩展能跑通：给 `AlertRules` 加第三条规则(如「连续 N 帧急加速」需跨帧状态)并注册进 demo，观察告警数变化

## 与真实生产形态的差距(诚实清单)

| 本平台 | 生产形态 | 说明 |
|--------|---------|------|
| `MetricsBus` 内存分区 | Kafka topic(多分区/副本/重平衡) | 语义复刻(分区保序/offset/积压)；真 Kafka 代码见主文档 3.3，标「未在本环境验证」 |
| `SourceStateCache` 内存 CHM | Redis Hash/String + TTL | 本平台单 JVM 演示；多实例共享需 Redis(ph18 ex01)，TTL 过期策略未涉及 |
| Netty 网关缺席(直接调 IngestService) | 网关按行解码后调接入 | Netty 网关形态见 [`examples/ex09`](../examples/ex09-netty-gateway/)(已实测) |
| 3 个数据源 × 400 帧 | 百万级节点集群 | 吞吐调优与背压见 examples/ex02(lane 模型) |
| 单 JVM 模块 | Spring Boot 多服务 + 服务发现 | 包一层 HTTP + Spring 装配即微服务(ph14/ph16)；部署形态见 ph19 模板 |
| demo 无 DB 持久化 | MySQL/时序库 | 状态缓存之外的历史数据需落库(ph13)，作业历史落时序库 |

## 扩展方向

- **加规则**：`AlertRules` 加「急加速告警」(需跨帧比较延迟)——体会「无状态规则 vs 跨帧状态」的引擎边界；生产上规则可用 SPI 装载(examples/ex04)
- **接入换 Netty**：把 `IngestService.submit` 接到 examples/ex09 网关的 handler 里，让行文本真的从 TCP 进来
- **版本发布 与节点状态联动**：批次推进时同步把数据源状态置 UPDATING/回 ONLINE(本平台是「档案固件生效」，全状态机见 examples/ex01)
- **多实例消费组**：MetricsConsumer 加并发 worker + 分区重平衡(练习 sol-04 已做消费组)，替换掉单消费者 drain
- **真 Kafka/Redis 落地**：按主文档 3.3/3.5 的代码与 docker 命令(标注「未在本环境验证」)把总线与缓存换真件，再接 ph19 部署模板上云——这就是本收官项目通往真实数据平台平台的最后一段路
