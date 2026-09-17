# contracts —— OceanVerse 平台契约模块

> 全平台数据"宪法"的代码载体。独立 go.mod，供 device-gateway、device-codec（第 1 阶段收尾）、
> 及后续 Flink/Java 侧参考引用。修改本模块必须走评审。

## 包结构

```
contracts/
├── go.mod                  # module github.com/Mosslau/OceanVerse/contracts（零外部依赖）
└── vehicle/
    ├── vehicle.go          # VehicleReport + ReportData + Validate + SchemaV1（信封 v2）
    └── vehicle_test.go     # 契约校验单测
```

## 历史

原位于 `ingest/device-gateway/internal/model/vehicle.go`。Go 的 `internal` 包编译器私有，
device-codec 等兄弟模块无法 import → 被迫搬家（设计文档 §11.4）。2026-09-17 迁入，内容一行未改。

## 引用方式（同仓模块）

```go
// go.mod:
require github.com/Mosslau/OceanVerse/contracts v0.0.0-00010101000000-000000000000
replace github.com/Mosslau/OceanVerse/contracts => ../../contracts   // 按实际相对路径调整

// 代码:
import "github.com/Mosslau/OceanVerse/contracts/vehicle"
```

## 纪律

- 契约字段全可选（omitempty），新增字段向后兼容；删除/改语义 = 新版本
- `schema_version` 未知版本拒绝（fail-fast），信封 v2 死线：首批固件冻结前（设计文档 §4.4）
- 二进制线协议 L1 ↔ 本契约 L2 的映射：《ingest/device-gateway/docs/GB32960-二进制协议与字段映射-v1.md》（已定稿 v1.4）
