# P2 设备数据纵切（数据平台 · 对应 D2/D3 的一部分）

> 状态：🚧 进行中
> 所属平台与单元：data-platform · P2 设备数据纵切（类别：期，对应 D2/D3 的部分验收）
> 对应文档：[通用数据平台建设路线](../../data-platform/通用数据平台建设路线.md)（D2/D3）· [车联网与机器人数据域技术增量](../../车联网与机器人数据域技术增量.md)（§3 轴 A、§14 最小纵切）

## 1. 目标

跑通一条**最小端到端纵切**，证明设备数据域的三个第一性设计成立：

1. **raw 不可变**：原始帧原样落 `var/raw/<run_id>/frames.jsonl`，同一 run 不允许重写；
2. **按当时的协议版本解码**：同一条报文按 `dbc.v1` 解是 42.0V，按 `dbc.v2` 解是 21.0V；
3. **重放幂等**：同一批数据重复写入，行数不变。

链路：

```text
模拟器（10 车 × 10 帧 × 50 信号）
  → raw JSONL（只追加）
  → Kafka topic（mosaic.device.frames.<run_id>）
  → 解码（协议登记簿）
  → PG 长表 signal_long + 故障表 fault_events + 账本 pipeline_ledger
```

**一句话验收**：`./slice.sh` 输出 `signal_rows=5000 fault_events=2 idempotent=True differs=True`，且 `./query.sh` 能查到长表、故障与账本。

## 2. 范围与不做

**做**：

- 合成原始帧（原始计数，不是物理值），确定性种子；
- 协议登记簿（`registry/protocols.json`）：`dbc.v1` / `dbc.v2` 两版；
- 解码为长表 `(device_id, signal_id, ts, value, quality, protocol_version, codec_version)`；
- 越界信号标 `quality=suspect` 但不丢弃；
- 故障判定（电池过压 `P0A1`、电机过温 `P0A2`）；
- PG 长表 + 故障表 + 账本；重放幂等；
- 版本绑定演示（同一帧 v1 vs v2）。

**不做**：

- Iceberg / SeaTunnel（D2/D3 的正式接入；本纵切先用 PG 承接长表）；
- Flink 流式解码（当前是批式：Kafka → 消费 → 解码）；
- 真实 DBC 二进制解析（当前用 JSON 帧模拟 CAN 原始计数）；
- 边缘采样、补传、时空索引（后续 D3/D4 增量）；
- 告警运营与工单闭环（AI 平台 D8/D9）。

## 3. 技术栈

| 层 | 选择 | 说明 |
|---|---|---|
| 模拟/解码 | Python 3.9 标准库 | 零第三方依赖 |
| 消息 | Kafka 4.4（共享底座） | 用容器内 `kafka-console-producer/consumer` 验证链路 |
| 存储 | PostgreSQL 16（共享底座） | 长表 / 故障 / 账本；D2 接 Iceberg 前的临时落点 |
| 编排 | `docker compose exec` | D3 正式接入时换 SeaTunnel/JDBC |
| 测试 | `unittest` | 12 项，不依赖 Docker |

## 4. 系统架构

```text
simulate() ──► raw JSONL（WORM）
     │
     └──► kafka-console-producer ──► topic: mosaic.device.frames.<run_id>
                                          │
                                          ▼
                              kafka-console-consumer
                                          │
                              ProtocolRegistry.decode_frame()
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                           ▼
            signal_long（PG 长表）                     fault_events（PG）
                    └──────────────► pipeline_ledger（PG 账本）◄──┘
```

表结构：

| 表 | 主键 | 说明 |
|---|---|---|
| `signal_long` | `(device_id, signal_id, ts)` | 长表，不做宽表；带 `protocol_version` / `codec_version` |
| `fault_events` | `event_id` | `device-ts-code` 确定性 ID，重放不重复 |
| `pipeline_ledger` | 自增 | `trace_id` + `stage` + `detail`，每段可查 |

## 5. 前置与复用

- **前置**：共享 D0 底座 [`../../infra/compose/`](../../infra/compose/)（Kafka / PG / Redis / Prometheus / Grafana）；
- **复用**：契约口径沿用 [P1 契约内核](../P1-contract-kernel/README.md) 的 `Envelope` / `TableRef`（本纵切暂未做 HTTP 接入，只复用字段命名）；
- **领域设计**：三轴与登记簿来自 [技术增量 §3](../../车联网与机器人数据域技术增量.md)，纵切步骤对应 §14 的 1–4 步。

## 6. 验收标准

| 编号 | 通过标准 | 当前状态 | 证据 |
|---|---|---|---|
| `V3-6` | 协议换版后，历史数据仍按旧版解释 | ✅（纵切级） | 同一帧 `raw=420`：`v1=42.0` / `v2=21.0`，`differs=True`；帧自带 `protocol=dbc.v1` |
| `V3-3` | 重放幂等 | ✅（纵切级） | 同一批 5000 行重复写入：`before=5000 after=5000 unchanged=True` |
| `V2-4` | raw 不可变 | ✅（纵切级） | `var/raw/<run_id>/` 用 `mkdir(exist_ok=False)` + 文件 `x` 模式，同一 run 不可重写 |
| `V3-4` | 流式解码 | 🟡 | 已做「消费 → 解码」，但是批式；Flink 流式未接 |
| `V3-1` | 源 → Kafka → Iceberg | 🟡 | Kafka 已通，Iceberg/SeaTunnel 未接，当前落 PG |
| `V2-6` | 1 亿点轨迹时空查询 | ⬜ | 时空索引与轨迹表未做 |

**复现命令**：

```bash
cd engineering/data-platform/P2-device-slice
./test.sh      # 12 项单元测试（不需要 Docker）

# 先确认共享底座已起：engineering/infra/compose/up.sh
./slice.sh     # 默认 10 车 × 10 帧 × 50 信号
./query.sh     # 查长表 / 故障 / 版本分布 / 账本
```

实测输出（2026-11-11）：

```text
[raw] .../var/raw/20261111T055535Z-93d6e4/frames.jsonl (100 frames)
[kafka] topic=mosaic.device.frames.20261111T055535Z-93d6e4 produced=100 consumed=100
[pg] signal_rows=5000 fault_events=2
[idempotency] before=5000 after=5000 unchanged=True
[version] raw=420 v1=42.000 v2=21.000 differs=True
```

## 7. 实施笔记

- **2026-11-11 新建**：模拟器 / 登记簿 / 纵切链路 / 12 项测试；首次跑通 Kafka → 解码 → PG。
- **踩坑：主键冲突导致第二次运行「0 行」**。模拟器用固定起始时间时，两次 run 的 `(device, signal, ts)` 完全相同，`on conflict do nothing` 把第二批全部跳过——这恰好证明了幂等，但会让演示误以为没写进去。改为 CLI 默认用当前 UTC 秒作为起始时间（`--start` 可覆盖），单元测试仍用固定时间保证确定性。
- **端口**：沿用共享底座的 19092/15432；Kafka topic 按 run_id 隔离，避免消费者读到历史批次。
- **待办**：
  1. 接 Iceberg（`parsed` 区）与 SeaTunnel，把 `signal_long` 从 PG 迁到湖表（`V3-1`）；
  2. 用 Flink 做流式解码与 CEP 故障判定（`V3-4`/`V4-8`）；
  3. 补 DBC 二进制帧解析（当前是 JSON 原始计数）；
  4. 把 `Envelope` 接进来：设备接入走 P1 的 `/v1/echo`，形成「契约 → 纵切」的同一条链。
