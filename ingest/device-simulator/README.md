# device-simulator —— 车端数据模拟器（接入层仿真工具）

> 模拟真实车队，三条通道各一个产生器；共享 `internal/simdata`（数据分布）与
> `internal/simframe`（GB/T 32960 二进制造帧），保证跨通道数据分布一致、可横向对比。
> 本模块是**测试工具**，不进生产部署；与 device-codec 解码器互为对拍（独立实现同一规格）。

## 三个产生器

| 命令 | 通道 | 用途 |
|---|---|---|
| `cmd/http-simulator` | HTTP → 网关 `/api/v1/vehicle/report` | 联调 + HTTP 通道压测 |
| `cmd/mqtt-simulator` | MQTT(JSON) → EMQX `ov/{vin}/{status,battery,fault}` | 完整链路验证 + 长连接压测 |
| `cmd/bin-simulator` | MQTT(GB/T 32960 二进制帧) → EMQX `ov/{vin}/bin` | 二进制链路联调/压测/对拍数据源 |

## 用法

```bash
go run ./cmd/http-simulator -target http://localhost:18080 -devices 1000 -interval 5s -duration 60s
go run ./cmd/mqtt-simulator -broker tcp://localhost:1883 -devices 1000 -interval 5s -duration 60s
go run ./cmd/bin-simulator   -broker tcp://localhost:1883 -devices 100 -interval 10s -duration 60s
```

压测方法学与 Rancher 端口转发限制见 `deploy/README.md` Q9；1883 被占时用 `EMQX_MQTT_PORT`（Q10）。

## 目录

```
ingest/device-simulator/
├── cmd/http-simulator/     # HTTP 通道
├── cmd/mqtt-simulator/     # MQTT JSON 通道
├── cmd/bin-simulator/      # MQTT 二进制帧通道
└── internal/
    ├── simdata/            # 仿真数据分布(车速/SOC/电池明细/充电/工况)
    └── simframe/           # GB/T 32960 造帧器(§5/§5.1/§5.2 布局 + 黄金样本测试)
```
