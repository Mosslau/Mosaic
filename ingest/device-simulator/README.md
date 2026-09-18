# device-simulator —— 车端数据模拟器（接入层仿真工具）

> 📚 **简称约定**：《接入层设计》= 《../docs/接入层与车端接入网关设计-v1.md》｜《GB32960 映射》= 《../docs/GB32960-二进制协议与字段映射-v1.md》。下文以这两个简称标注跨文档引用。
> 📐 **设计见**《接入层设计》§10.1（模拟与验证方案）；帧规格见《GB32960 映射》

> 模拟真实车队，三条通道各一个产生器；共享 `internal/simdata`（数据分布）与
> `internal/simframe`（GB/T 32960 二进制造帧），保证跨通道数据分布一致、可横向对比。
> 本模块是**测试工具**，不进生产部署；与 device-codec 解码器互为对拍（独立实现同一规格）。

## 三个产生器 + 一个自检工具

| 命令 | 通道 | 用途 |
|---|---|---|
| `cmd/http-simulator` | HTTP → 网关 `/api/v1/vehicle/report` | 联调 + HTTP 通道压测 |
| `cmd/mqtt-simulator` | MQTT(JSON) → EMQX `ov/{vin}/{status,battery,fault}` | 完整链路验证 + 长连接压测 |
| `cmd/bin-simulator` | MQTT(GB/T 32960 二进制帧) → EMQX `ov/{vin}/bin` | 二进制链路联调/压测/对拍数据源 |
| `cmd/security-check` | MQTT(TLS 8883) | 公网路径安全基线六项自检（《接入层设计》§8.3） |

## 用法

```bash
go run ./cmd/http-simulator -target http://localhost:18080 -devices 1000 -interval 5s -duration 60s
go run ./cmd/mqtt-simulator -broker tcp://localhost:1883 -devices 1000 -interval 5s -duration 60s
go run ./cmd/bin-simulator   -broker tcp://localhost:1883 -devices 100 -interval 10s -duration 60s
```

压测方法学与 Rancher 端口转发限制见 `deploy/README.md` Q9；1883 被占时用 `EMQX_MQTT_PORT`（Q10）。

## 两个身份形态（`internal/simconn` 统一）

| 形态 | 连接方式 | clientid | 凭证 | topic |
|---|---|---|---|---|
| dev（内网联调） | 明文 1883 | `dev-{VIN}` | 匿名 | `ov/{VIN}/…` |
| 生产（公网演练） | TLS 8883 | `{VIN}` | username=VIN / password=`pw-{VIN}` | 同上 |

```bash
# 生产形态: TLS + 一车一密(clientid/username=VIN); 需先 deploy/emqx/seed-users.sh
go run ./cmd/bin-simulator -tls -cacert ../../deploy/emqx/certs/ca.crt \
  -broker localhost:8883 -devices 20 -interval 2s -duration 20s

# 公网路径安全基线自检(六项: 正向连通/匿名拒/错密码拒/越权拒且断开/明文打 8883 失败/dev 回归)
go run ./cmd/security-check -vin OV20260001 -other-vin OV00000099
```

## 全参数表

**`cmd/http-simulator`（HTTP 通道）**

| 参数 | 默认 | 说明 |
|---|---|---|
| `-target` | `http://localhost:18080` | 网关地址（本机开发固定 18080） |
| `-devices` | 100 | 虚拟车辆数 |
| `-interval` | 5s | 单设备上报间隔 |
| `-duration` | 60s | 总时长（0=不限，Ctrl+C 停） |

**`cmd/mqtt-simulator`（MQTT JSON） / `cmd/bin-simulator`（二进制帧）**

| 参数 | 默认 | 说明 |
|---|---|---|
| `-broker` | `tcp://localhost:1883` | 本机 1883 被占时用 `tcp://localhost:11883` |
| `-devices` / `-interval` / `-duration` | 100 / 5s（bin 为 10s）/ 60s | bin 默认 10s = 国标频率基线 |
| `-fault-pct` | 0.01 | JSON: 附带故障消息概率；bin: 附带 0x07 报警信息体概率 |
| `-tls` | false | 公网形态：TLS + 一车一密（clientid=username=VIN） |
| `-cacert` | `../../deploy/emqx/certs/ca.crt` | TLS 校验用自签 CA |
| `-password-prefix` | `pw-` | 一车一密密码前缀（与 `seed-users.sh` 一致） |

**`cmd/security-check`（公网基线自检）**

| 参数 | 默认 |
|---|---|
| `-tls-broker` / `-plain-broker` | `localhost:8883` / `localhost:11883` |
| `-cacert` | `../../deploy/emqx/certs/ca.crt` |
| `-vin` / `-other-vin` | `OV20260001` / `OV00000099` |
| `-password-prefix` / `-timeout` | `pw-` / 8s |

**期望输出与端到端示例**：见《../docs/接入层示例集-v1.md》§5~§6（含实测输出）。

## 设计要点与不变量

| 要点 | 说明 |
|---|---|
| 工具不进生产 | 独立模块，不参与部署；与生产代码只共享契约 |
| 两身份形态 | dev（`dev-{VIN}` 匿名明文）↔ 生产（`clientid=username=VIN` + TLS），由 `internal/simconn` 统一 |
| 造坏数据 | 刻意注入欠压/高温/故障/能量回收，让告警与清洗链路有真实样本 |
| 对拍机制 | `simframe` 造帧器与 codec 解码器**独立实现同一规格**，黄金样本双端各存一份 |
| 设计出处 | 《接入层设计》§10.1（模拟与验证方案）；帧规格《GB32960 映射》§5/§5.1/§5.2 |

## 目录

```
ingest/device-simulator/
├── cmd/http-simulator/     # HTTP 通道
├── cmd/mqtt-simulator/     # MQTT JSON 通道
├── cmd/bin-simulator/      # MQTT 二进制帧通道
├── cmd/security-check/     # 公网安全基线自检(《接入层设计》§8.3)
└── internal/
    ├── simconn/            # MQTT 连接助手(两身份形态: dev 匿名 / 生产 TLS+一车一密)
    ├── simdata/            # 仿真数据分布(车速/SOC/电池明细/充电/工况)
    └── simframe/           # GB/T 32960 造帧器(《GB32960 映射》§5/§5.1/§5.2 布局 + 黄金样本测试)
```
