# ingest/device-contracts —— 平台契约的 Go 绑定

> 📚 **简称约定**：《接入层设计》= 《../docs/01-接入层设计-v1.md》｜《GB32960 映射》= 《../docs/02-GB32960协议规格-v1.md》｜《示例集》= 《../docs/03-验收示例集-v1.md》。下文以这三个简称标注跨文档引用。
> 📐 **设计见**《接入层设计》§4（L2 契约与版本化）

> 根 `contracts/`（语言无关：proto/JSON Schema）的 **Go 投影**。
> 独立 go.mod，供 device-gateway、device-codec、simulator 等本仓 Go 模块引用。
> 修改本模块必须走评审（改动 = 契约改动）。

## 1. 包结构

```text
ingest/device-contracts/
├── go.mod                  # module github.com/Mosslau/Mosaic/ingest/device-contracts（零外部依赖）
└── vehicle/
    ├── vehicle.go          # VehicleReport + ReportData + Validate + SchemaV1（信封 v2）
    └── vehicle_test.go     # 契约校验单测
```

## 2. 历史

原位于 `ingest/device-gateway/internal/model/vehicle.go`（internal 私有，兄弟模块无法 import）
→ 2026-09-17 迁至根 `contracts/` → 同日按"语言无关在根、Go 绑定随消费者"拆分到本目录。

## 3. 引用方式（同仓模块）

```go
// go.mod:
require github.com/Mosslau/Mosaic/ingest/device-contracts v0.0.0-00010101000000-000000000000
replace github.com/Mosslau/Mosaic/ingest/device-contracts => ../device-contracts   // 按实际相对路径调整

// 代码:
import "github.com/Mosslau/Mosaic/ingest/device-contracts/vehicle"
```

## 4. 契约设计（两层/结构/字段/版本）

### 4.1 两层契约

| 层 | 内容 | 定义处 |
|---|---|---|
| **L1 线协议** | 二进制帧（GB/T 32960 框架 + 自定义单元） | 《02-GB32960协议规格-v1.md》 |
| **L2 标准契约** | `VehicleReport` JSON | 《接入层设计》§4.1 + `ingest/device-contracts/vehicle/vehicle.go` |

关系：codec 是两层之间的唯一翻译点；**L1 怎么变，L2 不变**（信封一份）。

### 4.2 结构设计

```json
{ "vin": "OV20260001", "ts": 1789619400, "type": "vehicle_status",
  "schema_version": "v1", "model": "A100",
  "data": { "...各 type 用各自子集, 全可选..." } }
```

| 字段 | 策略 | 理由 |
|---|---|---|
| `vin` | 必填，5~32 字符，Kafka 分区 key | 保序锚点 + 幂等键之一 |
| `ts` | 必填，Unix 秒，容差 [−7 天, +5 分钟] | 允许补发，拒绝明显错时 |
| `type` | 必填枚举（5 值） | 下游分发依据；L1 多类型映射到少量稳定 L2 类型 |
| `data` | **全可选**（omitempty） | 新增字段向后兼容；不同 type 用不同子集 |
| `schema_version` | 缺省回填 `v1`，未知拒绝 | 信封 v2；死线=首批固件冻结前 |
| `model` | 暂可缺省，第 4 阶段 Registry 后必填 | 多车型演进钩子 |

### 4.3 字段语义与校验（节选）

| 字段 | 范围/语义 |
|---|---|
| `speed` / `soc` | [0,300] km/h；[0,100] % |
| `current` | 放电正/充电负 |
| `temp_max/min` | [−40,150] ℃ |
| `lng` / `lat` | WGS84，[−180,180] / [−90,90] |
| `fault_codes` | `type=fault` 时必填非空；hex 大写无前缀 |
| `cell_voltages` / `probe_temps` | 元素 [0,5] V / [−40,150] ℃（0x08/0x09 载体） |
| `remain_charge_min` / `charge_power` / `charge_kwh` / `slot_no` | [0,6000] / [0,100] / [0,100] / [1,254] |
| `ride_state` / `ride_mode` | `riding/parked/pushing/reverse`；`eco/standard/sport` |
| `motor_rpm` / `throttle` | [0,20000]；[0,100] |

### 4.4 版本策略

| 策略 | 做法 |
|---|---|
| 兼容优先 | 只增字段不改语义；删/改语义 = 新版本 |
| fail-fast | 网关与 codec 都拒绝未知版本（宁可拒绝也不猜） |
| 前移的时机 | 信封 v2 字段**提前**到首批固件冻结前（固件烧进车就改不动） |
| 声明式收口 | 第 4 阶段 Schema Registry；中间态"轻量查表层"可提前 |

### 4.5 代码组织与治理

| 位置 | 内容 | 谁消费 |
|---|---|---|
| 根 `contracts/` | 语言无关形态（proto / JSON Schema，占位） | 未来各语言绑定 |
| `ingest/device-contracts/` | Go 绑定（`VehicleReport` + Validate） | gateway / codec / simulator |

纪律：契约改动走评审；Go 绑定随消费者放，语言无关形态放根（"全平台宪法"是结构事实，不只是文档表述）。

---

## 5. 设计要点与不变量

| 要点 | 说明 |
|---|---|
| 信封一份 | 无论 L1 是 JSON 还是二进制帧，经网关/codec 后都是同一个 `VehicleReport` |
| 字段全可选 | 新增字段向后兼容；删/改语义 = 新版本（信封 v2 的 `schema_version`） |
| fail-fast | 未知版本拒绝而非猜测（网关与 codec 都执行） |
| 单一真相 | 本模块是契约的 Go 绑定；语言无关形态在根 `contracts/`；L1↔L2 映射在《GB32960 映射》 |
| 设计出处 | 《接入层设计》§4（L2 契约与版本化）、§4.4（信封 v2 死线） |

## 6. 纪律

- 契约字段全可选（omitempty），新增字段向后兼容；删除/改语义 = 新版本
- `schema_version` 未知版本拒绝（fail-fast），信封 v2 死线：首批固件冻结前（《接入层设计》§4.4）
- 二进制线协议 L1 ↔ 本契约 L2 的映射：《GB32960 映射》（已定稿 v1.4）

## 7. 延伸阅读（为什么这么设计）

- （《接入层设计》§4.4）

> 本手册只讲"怎么跑/怎么验"；上面的层文档讲"为什么"。设计与规格的权威在那两篇，本手册不复制其内容。
