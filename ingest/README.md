# ingest 接入层 —— OceanVerse 的数据国门

> 📐 完整设计文档：《device-gateway/docs/接入层与车端接入网关设计-v1.md》
> 对应架构总览能力域①数据集成 / 架构图 Access Layer
> 本层职责: 把"杂乱的设备流量"变成"干净、可信、有节制的标准数据流"
> 本层不含业务逻辑——数据进来什么样, 进 Kafka 就什么样(除了清洗和标准化)

## 链路全景

```
                        ┌──────────────── 实时通道 ────────────────┐
                        │                                          │
 车端设备 ──HTTP────► device-gateway(鉴权→限流→校验) ──────────┐  │
                        │                                        │  │
 车端设备 ──MQTT───► EMQX(协议终结/连接管理/QoS)                │  │
                        │  规则引擎: SELECT * FROM "ov/+/..."    ▼  ▼
                        │  Webhook(密钥头+连接池+磁盘缓冲重试)  device-gateway
                        └────────────────────────────────────────│  │
                                                                 ▼  ▼
                                                          Kafka vehicle-report-raw
                                                          (Key=VIN, 同车同分区保序)

 离线通道(第 2 阶段): file-receiver(文件/多模态 → MinIO, 只元数据进 Kafka)
```

## 两条实时通道的职责边界

| | HTTP 通道 `/api/v1/vehicle/report` | MQTT 通道(EMQX → `/api/v1/mqtt/ingest`) |
|---|---|---|
| 适用设备 | App、充电桩、轻量设备 | 车端 T-BOX(长连接/弱网/省电) |
| 协议终结 | 网关直接终结 | **EMQX 终结**(连接/会话/QoS/遗嘱) |
| 设备鉴权 | 网关(token 白名单) | **EMQX**(认证链) + 网关验 webhook 密钥 |
| 单设备限流 | 网关令牌桶 | **EMQX 协议层**(rate_limit) |
| 契约校验/Kafka 写入 | 网关 | 网关(同一个 Validate, 同一个 producer) |

**核心设计: EMQX 管"连接", 网关管"治理"。** 数据契约、校验规则、Kafka 分区策略永远只有一份(网关), MQTT 只是多了一种"进门方式"。

## Topic 契约(MQTT 侧)

| Topic | 类型 | QoS | 理由 |
|---|---|---|---|
| `ov/{vin}/status` | 整车状态(周期) | 0 | 周期数据可丢, 网络开销最小 |
| `ov/{vin}/battery` | 电池 BMS 明细 | 0/1 | 视电池安全监控等级 |
| `ov/{vin}/fault` | 故障码(事件) | **1** | 事件必达; at-least-once 的重复由下游按 (vin,ts,fault_codes) 幂等 |

## 企业级四支柱

### 高性能
- EMQX 单节点百万级连接基线(Erlang/OTP 软实时)
- 网关→Kafka: 异步 + 攒批(200 条/50ms), HTTP 链路不被 Kafka 拖慢
- EMQX→网关: webhook 连接池 16 + hash 分配(同车消息同连接, 保序)
- 全链路无同步阻塞点, 唯一同步等待是"消息进内存队列"

### 可扩展
- 网关无状态: 水平扩 N 个副本, 前面挂 LB 即可(第 2 阶段 K8s HPA)
- EMQX 集群化: compose 再加 emqx-2 节点, `discovery_strategy=static` + seeds 即集群
- Kafka 扩容: 加分区即可(VIN 哈希天然均匀)
- 扩展顺序: 先扩 Kafka 分区 → 再扩网关副本 → 最后扩 EMQX 节点

### 稳定性
- **网关挂了**: EMQX webhook 256MB 磁盘缓冲 + 60s TTL 重试, 恢复后补投
- **Kafka 挂了**: 网关 202 语义下消息已在 Kafka 客户端缓冲; 网关返回 5xx 时 EMQX 重试
- **EMQX 挂了**: 设备 AutoReconnect(模拟器已实现); 生产 LB 健康检查摘除节点
- **重复消息**: QoS1 at-least-once 会重复 → 下游幂等(契约里 ts+vin 即幂等键)
- 优雅退出: SIGTERM → 停收流量 → 冲刷 Kafka 缓冲批次(10s 宽限)

### 可配置
- 网关 11 项配置全部环境变量(见 device-gateway/README 配置表), 无硬编码
- EMQX 全部行为(监听器/认证/规则/webhook)声明在 `deploy/emqx/emqx.conf` 一个文件
- topic 契约改动 = 改 emqx.conf 的 rule SQL + 重启, 不动代码

## 生产加固清单(本地模拟 → 生产差距)

| 项 | 本地(现在) | 生产(目标) |
|---|---|---|
| MQTT 传输 | 1883 明文 | 8883 TLS + 设备证书 |
| 设备认证 | 匿名(dev) | EMQX 内置库/对接车辆档案服务 HTTP 认证, 一车一密 |
| Topic 授权 | 无 ACL | 设备只能 pub `ov/${clientid}/#` |
| webhook 密钥 | 默认值 | 强随机 + 密钥轮换 |
| Kafka 持久性 | RequireOne | RequireAll + min.insync.replicas=2 |
| EMQX | 单节点 | 3 节点集群 + LB |
| 审计 | metrics | + 消息抽样落审计表(第 2 阶段控制面) |

## 目录

```
ingest/
├── README.md                    ← 本文件(接入层速览)
└── device-gateway/              ← Go 实时通道(HTTP + MQTT-webhook 双入口)
    ├── README.md                ← 运行/验证/压测/测试手册
    ├── docs/                    ← 设计文档(含 §12 企业级成熟度评估)
    ├── cmd/server               ← 网关主程序
    ├── cmd/simulator            ← HTTP 通道压测器
    ├── cmd/mqtt-simulator       ← MQTT 长连接压测器
    └── internal/                ← 治理流水线五件套(model/auth/ratelimit/kafka/metrics)
    (file-receiver 第 2 阶段加入: 离线通道)
```

## 当前状态（第 1 阶段）

| 项 | 状态 |
|---|---|
| 双通道链路 | ✅ HTTP + MQTT 已实现，编译通过 |
| 单元测试 | ✅ 5 包 30+ 用例（`go test ./...`，核心包覆盖 77~100%） |
| EMQX 声明式规则 | ✅ `deploy/emqx/emqx.conf`，启动自动加载 |
| 压测实测数字 | ⏳ 待回填（设计文档 §7.3 基线表） |
| 企业级成熟度 | 详见《device-gateway/docs/接入层与车端接入网关设计-v1.md》§12 |
