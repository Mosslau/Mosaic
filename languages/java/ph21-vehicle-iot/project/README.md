# ph21 阶段项目：车联网后台平台(vehicle-iot, 收官项目)

> 对应 roadmap §21「推荐项目」第一个「车联网后台平台」。本平台是 **Java 学习路线的收官项目**：把 ph01~ph20 的机制(并发/CHM/线程池、Netty 接入形态、SPI 规则、DDD 建模、Kafka 消费语义、OTA 状态机、运维聚合)按真实车联网数据链路组织成**一个纯 Java 可 javac 编译测试的模块集**。采用 ph18 秒杀 demo 的「纯 Java 可测先例」与 ph19 部署模板结构：模块边界即服务边界，全部内存实现、可离线跑、输出即验收。

## 需求

roadmap §21 示例骨架是 `车辆 → 接入服务 → Kafka → 清洗/告警/存储 → 后台平台`。本项目的模拟链路与它一一对应：

```text
3 台模拟车 ─并发─▶ IngestService(校验+去重) ─▶ TelemetryBus(按 VIN 分区≈Kafka)
        ─▶ TelemetryConsumer.drain ─▶ 状态缓存 + 轨迹 + 设备在线 + 告警引擎
OtaPlatform(版本库/批次/回滚/审计) ────────────────────────────┘
                OpsConsole(运维后台聚合) ◀── 各域只读快照
```

模块边界即「微服务切分」的教学切片(每个模块=一个限界上下文，ph20 DDD 落地)：

| project 模块 | 对应真实服务 | 用到的 ph01~ph20 机制 |
|--------------|-------------|----------------------|
| `DeviceRegistry` | 设备管理服务 | 聚合根 + 状态机 + CAS 更新(ph02/ph04/ph20 DDD) |
| `TelemetryFrame` | 协议层(网关解码后) | record + 量程校验(ph02/ph03) |
| `IngestService` | 接入服务 | 并发去重 + CAS + 计数(ph09/ph20 JMM) |
| `TelemetryBus` | Kafka topic | 按 key 分区、append-only、offset(ph17) |
| `TelemetryConsumer` | 遥测消费服务 | 先处理再 commit、积压 lag(ph17) |
| `VehicleStateCache` | Redis 实时状态缓存 | ConcurrentHashMap.compute 原子读改写(ph18/ph20 CHM) |
| `TrackStore` | 轨迹服务 | 每车历史点 + 并发队列(ph04) |
| `AlertEngine`/`AlertRules` | 告警规则引擎 | 规则可插拔(依赖倒置，ph20 SPI 思想) |
| `OtaPlatform` | OTA 管理平台 | 版本语义比较 + 批次状态机 + 审计 + 回滚(ph08/ph20) |
| `OpsConsole` | 运维后台 | 跨域聚合视图(ph08 Stream) |

## 目录结构

```text
project/
├── README.md
└── src/vehicleiot/
    ├── VehicleIotPlatformDemo.java   # 端到端演示 + 验收断言(14 项 PASS)
    ├── DeviceRegistry.java           # 设备注册/状态/固件(车辆档案聚合)
    ├── TelemetryFrame.java           # 遥测帧 record + 协议解码 + 量程校验
    ├── IngestService.java            # 接入服务：去重/坏帧拦截/投递总线
    ├── TelemetryBus.java             # 内存版 Kafka(8 分区，按 VIN 哈希)
    ├── TelemetryConsumer.java        # 消费服务：drain + 更新多下游
    ├── VehicleStateCache.java        # 实时状态缓存(CHM.compute 原子更新)
    ├── TrackStore.java               # 轨迹点存储(每车最近 N 点)
    ├── AlertRule.java                # 告警规则接口
    ├── AlertRules.java               # 内置两条规则(LowSoc / Overheat)
    ├── AlertEngine.java              # 规则求值 + 活跃告警表
    ├── OtaVersion.java               # 语义化版本号(可比较)
    ├── OtaPlatform.java              # OTA 平台：版本库 + 批次 + 状态机 + 审计
    └── OpsConsole.java               # 运维后台聚合视图
```

## 构建与运行(已验证)

验证环境：**OpenJDK 17.0.18(Homebrew，/opt/homebrew/opt/openjdk@17)**；零第三方依赖。

```bash
# 1. 编译(在 project/ 目录执行，产物输出到 /tmp)
JAVAC=/opt/homebrew/opt/openjdk@17/bin/javac
JAVA=/opt/homebrew/opt/openjdk@17/bin/java
$JAVAC -encoding UTF-8 -d /tmp/tl21-proj src/vehicleiot/*.java
# 2. 运行端到端演示(输出即验收报告)
$JAVA -cp /tmp/tl21-proj vehicleiot.VehicleIotPlatformDemo
# 3. 清理
rm -rf /tmp/tl21-proj
```

运行输出 14 行 `PASS ...`(见下方验收标准)并以 `ALL PASS: 14/14` 结束，另打印运维总览(6 车/在线 3/告警 2/无积压)。

## 功能清单

- [x] 设备管理：注册 6 台车、状态迁移(CAS 更新)、固件版本升级落档案
- [x] 车辆接入：3 台模拟车并发上报 1200 帧，坏帧拦截(6 条)与重发去重(9 条)计数精确
- [x] 数据总线：按 VIN 哈希入 8 分区；消费端先处理再推进 offset，drain 后 lag=0
- [x] 实时状态缓存：每台车最新帧收敛到 seq=400(乱序/旧帧不会覆盖)
- [x] 轨迹落库：1200 个轨迹点全部入库
- [x] 告警引擎：末帧注入 SOC=8% 与电机 135℃ → LOW_SOC 与 MOTOR_OVERTEMP 各 1 条活跃告警
- [x] OTA 平台：版本递进发布(1.4.0→2.0.0→2.2.0)、批次推进、2 成功 1 失败、失败车回滚(ROLLED_BACK)、成功车固件生效
- [x] 运维后台：跨域聚合读数(车辆/在线/告警/积压)与「每车状态 + OTA 进度」明细

## 验收标准

- `java -cp /tmp/tl21-proj vehicleiot.VehicleIotPlatformDemo` 输出 14 行 PASS 且以 `ALL PASS: 14/14` 结束(本机实测稳定)
- 你能回答三个「为什么」(对照主文档 3.x)：
  1. 为什么 `IngestService` 用「每车 `AtomicLong` + CAS」而非锁就能并发去重？(`computeIfAbsent` + `compareAndSet`，ph20 CHM 语义)
  2. 为什么消费端「处理完一批再推进 offset」，顺序反了会怎样？(先 commit 后处理 = 崩溃即丢数据，ph17)
  3. 为什么 `VehicleStateCache.update` 用 `compute` 一段式而非 `get + put`？(两段之间有竞态窗口，ph20 3.6)
- 加一个扩展能跑通：给 `AlertRules` 加第三条规则(如「连续 N 帧急加速」需跨帧状态)并注册进 demo，观察告警数变化

## 与真实生产形态的差距(诚实清单)

| 本平台 | 生产形态 | 说明 |
|--------|---------|------|
| `TelemetryBus` 内存分区 | Kafka topic(多分区/副本/重平衡) | 语义复刻(分区保序/offset/积压)；真 Kafka 代码见主文档 3.3，标「未在本环境验证」 |
| `VehicleStateCache` 内存 CHM | Redis Hash/String + TTL | 本平台单 JVM 演示；多实例共享需 Redis(ph18 ex01)，TTL 过期策略未涉及 |
| Netty 网关缺席(直接调 IngestService) | 网关按行解码后调接入 | Netty 网关形态见 [`examples/ex09`](../examples/ex09-netty-gateway/)(已实测) |
| 3 台车 × 400 帧 | 百万级车队 | 吞吐调优与背压见 examples/ex02(lane 模型) |
| 单 JVM 模块 | Spring Boot 多服务 + 服务发现 | 包一层 HTTP + Spring 装配即微服务(ph14/ph16)；部署形态见 ph19 模板 |
| demo 无 DB 持久化 | MySQL/时序库 | 状态缓存之外的历史数据需落库(ph13)，轨迹落时序库 |

## 扩展方向

- **加规则**：`AlertRules` 加「急加速告警」(需跨帧比较车速)——体会「无状态规则 vs 跨帧状态」的引擎边界；生产上规则可用 SPI 装载(examples/ex04)
- **接入换 Netty**：把 `IngestService.submit` 接到 examples/ex09 网关的 handler 里，让行文本真的从 TCP 进来
- **OTA 与设备状态联动**：批次推进时同步把车辆状态置 UPDATING/回 ONLINE(本平台是「档案固件生效」，全状态机见 examples/ex01)
- **多实例消费组**：TelemetryConsumer 加并发 worker + 分区重平衡(练习 sol-04 已做消费组)，替换掉单消费者 drain
- **真 Kafka/Redis 落地**：按主文档 3.3/3.5 的代码与 docker 命令(标注「未在本环境验证」)把总线与缓存换真件，再接 ph19 部署模板上云——这就是本收官项目通往真实车联网平台的最后一段路
