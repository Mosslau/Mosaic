# ingest/device-contracts —— 平台契约的 Go 绑定

> 根 `contracts/`（语言无关：proto/JSON Schema）的 **Go 投影**。
> 独立 go.mod，供 device-gateway、device-codec、simulator 等本仓 Go 模块引用。
> 修改本模块必须走评审（改动 = 契约改动）。

## 包结构

```
ingest/device-contracts/
├── go.mod                  # module github.com/Mosslau/OceanVerse/ingest/device-contracts（零外部依赖）
└── vehicle/
    ├── vehicle.go          # VehicleReport + ReportData + Validate + SchemaV1（信封 v2）
    └── vehicle_test.go     # 契约校验单测
```

## 历史

原位于 `ingest/device-gateway/internal/model/vehicle.go`（internal 私有，兄弟模块无法 import）
→ 2026-09-17 迁至根 `contracts/` → 同日按"语言无关在根、Go 绑定随消费者"拆分到本目录。

## 引用方式（同仓模块）

```go
// go.mod:
require github.com/Mosslau/OceanVerse/ingest/device-contracts v0.0.0-00010101000000-000000000000
replace github.com/Mosslau/OceanVerse/ingest/device-contracts => ../device-contracts   // 按实际相对路径调整

// 代码:
import "github.com/Mosslau/OceanVerse/ingest/device-contracts/vehicle"
```

## 纪律

- 契约字段全可选（omitempty），新增字段向后兼容；删除/改语义 = 新版本
- `schema_version` 未知版本拒绝（fail-fast），信封 v2 死线：首批固件冻结前（设计文档 §4.4）
- 二进制线协议 L1 ↔ 本契约 L2 的映射：《ingest/docs/GB32960-二进制协议与字段映射-v1.md》（已定稿 v1.4）
