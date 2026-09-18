# contracts/ —— OceanVerse 平台契约库（语言无关）

> 全平台数据"宪法"的**语言无关载体**。这里不放任何具体语言的代码。

## 分工

| 位置 | 内容 | 语言 |
|---|---|---|
| `contracts/`（本目录） | 契约的**语言无关形态**：proto 文件（第 2 阶段 gRPC 内部通道）、JSON Schema（信封 v2 声明式，Schema Registry 前提） | 无 |
| `ingest/device-contracts/` | 契约的 **Go 绑定**（`vehicle.VehicleReport` + Validate），供 device-gateway / device-codec / simulator 引用 | Go |

## 规则

- 语言无关形态是源头，各语言绑定是其投影；改契约先改这里，再同步绑定
- 现阶段源头文档 = 《ingest/docs/02-GB32960协议规格-v1.md》（L1）+《接入层设计》§4（L2）
- 目录暂以本 README 占位，proto/JSON Schema 随第 2 阶段 gRPC / Schema Registry 落地进入
