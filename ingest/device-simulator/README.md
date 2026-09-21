# device-simulator —— 车端数据模拟器（接入层仿真工具）

> 📚 **简称约定**：《接入层设计》= 《../docs/01-接入层设计-v1.md》｜《GB32960 映射》= 《../docs/02-GB32960协议规格-v1.md》｜《示例集》= 《../docs/03-验收示例集-v1.md》。下文以这三个简称标注跨文档引用。
> 📐 **设计见**《接入层设计》§10.1（模拟与验证方案）；帧规格见《GB32960 映射》

> 模拟真实车队，三条通道各一个产生器；共享 `internal/simdata`（数据分布）与
> `internal/simframe`（GB/T 32960 二进制造帧），保证跨通道数据分布一致、可横向对比。
> 本模块是**测试工具**，不进生产部署；与 device-codec 解码器互为对拍（独立实现同一规格）。

## 1. 三个产生器 + 一个自检工具

| 命令 | 通道 | 用途 |
|---|---|---|
| `cmd/http-simulator` | HTTP → 网关 `/api/v1/vehicle/report` | 联调 + HTTP 通道压测 |
| `cmd/mqtt-simulator` | MQTT(JSON) → EMQX `ov/{vin}/{status,battery,fault}` | 完整链路验证 + 长连接压测 |
| `cmd/bin-simulator` | MQTT(GB/T 32960 二进制帧) → EMQX `ov/{vin}/bin` | 二进制链路联调/压测/对拍数据源 |
| `cmd/security-check` | MQTT(TLS 8883) | 公网路径安全基线六项自检（《接入层设计》§8.3） |

## 2. 用法

```bash
go run ./cmd/http-simulator -target http://localhost:18080 -devices 1000 -interval 5s -duration 60s
go run ./cmd/mqtt-simulator -broker tcp://localhost:1883 -devices 1000 -interval 5s -duration 60s
go run ./cmd/bin-simulator   -broker tcp://localhost:1883 -devices 100 -interval 10s -duration 60s
```

Rancher 宿主转发层上限 ≈185 连接/端口，大并发压测必须在容器网内跑；1883 被占时用 `EMQX_MQTT_PORT`（`deploy/.env`）。

## 3. 两个身份形态（`internal/simconn` 统一）

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

## 4. 造数策略（怎么"造"数据）

### 4.1 为什么需要它 / 有哪些工具

没有真实车队时，模拟器是**唯一可控的压力与形态来源**；它同时充当 codec 的**对拍数据源**（独立实现同一份协议规格）。

| 工具 | 通道 | 用途 |
|---|---|---|
| `cmd/http-simulator` | HTTP → 网关 | 联调 + HTTP 通道压测 |
| `cmd/mqtt-simulator` | MQTT(JSON) → EMQX | 完整链路验证 + 长连接压测 |
| `cmd/bin-simulator` | MQTT(GB/T 32960 帧) → EMQX | 二进制链路联调/压测/对拍 |
| `cmd/security-check` | MQTT(TLS 8883) | 公网安全基线六项自检 |

三者共享 `internal/`：`simdata`（数据分布）+ `simframe`（造帧）+ `simconn`（连接/身份）。

### 4.2 虚拟车辆模型

| 策略 | 做法 | 理由 |
|---|---|---|
| VIN 规则 | `OV%08d`（0~N） | 与真实 VIN 规则解耦，便于按序号批量灌凭证 |
| 独立随机源 | 每车 `rand.NewPCG(id, id>>32)` | 各车数据分布独立可复现，压测可重放 |
| 随机相位 | 首次发送前随机 jitter（0~interval） | 防千车同刻齐发（惊群） |
| 分批爬坡 | 每批 256 台、批间隔 100ms | 连接风暴削峰（真实设备行为） |
| SOC 演化 | 每周期掉 0.01~0.06%，<5% 触发"换电"回满 | 模拟真实骑行/换电闭环，让充电/满电分支被覆盖 |

### 4.3 数据分布策略（造什么样的数）

| 数据 | 分布规则 | 设计意图 |
|---|---|---|
| 车速 | 0~45 km/h | 两轮车市区骑行，覆盖驻车/行驶两态 |
| 电压/电流 | 55~67V；放电 2~12A | 覆盖 48V/60V 平台；电流符号遵循契约（放电正） |
| 单体电压 | 16 串，名义 3.45V±50mV | §4.3 数据分布策略 |
| 欠压注入 | 5% 概率一节 <2.5V | 供"告警链路"演练（不是只造健康数据） |
| 探针温度 | 4 路，基线 25~35℃；充电 +5~10℃ | 覆盖充电温升 |
| 高温注入 | 1% 概率 >60℃ | 对应第 1 阶段 Flink 作业"高温电池"指标 |
| 充电业务 | SOC>99.9 视为充电完成窗口，附带 0x80（剩余时间/功率/电量/桩号/站号/仓号） | 让 charging 分支有真实样本 |
| 工况 work | 由车速反推转速/功率；3% 概率造能量回收（负转矩） | 覆盖 work 分支与有符号字段 |
| 故障 | 1% 概率附带 0x07 报警（E1001） | 事件类数据必达性验证（QoS1） |

### 4.4 造帧策略（`simframe`）

| 策略 | 做法 |
|---|---|
| 帧骨架 | `## (2B) + 命令单元(2B) + VIN(17B 左对齐右补 0x00) + 加密(1B) + 长度(2B 大端) + 数据单元 + BCC(1B)` |
| BCC | 命令单元首字节至数据单元末字节逐字节异或（发送端算、接收端验） |
| 时间字段 | 6B `yy MM dd HH mm ss`，**GMT+8 明文**（国标口径，《GB32960 映射》§8-③） |
| 一帧多信息体 | 0x01+0x05+0x06+0x08+0x09+0x81 常规串联，0x80/0x07 条件附带 |
| 无效值约定 | 本项目不上报的国标字段填 0xFF/0xFFFF，由 codec 丢弃 |
| 黄金样本 | 固化 58B（0x08+0x09）与 142B（全 8 类信息体）两份 hex，与 codec 双端各存一份**对拍** |

### 4.5 连接与压测策略

| 策略 | 做法 | 理由 |
|---|---|---|
| 两个身份形态（`simconn` 统一） | dev：`clientid=dev-{VIN}` + 匿名 + 明文；生产：`clientid=username=VIN` + `pw-{VIN}` + TLS | 同一套模拟器覆盖内网联调与公网演练，零代码切换 |
| QoS | 周期状态 QoS0；故障 QoS1 | 周期可丢、事件必达（at-least-once，下游幂等） |
| 发布等待语义 | 只等本地排队（`WaitTimeout`），不等端到端 ACK | 压测测吞吐，不被逐条 RTT 拖死 |
| 连接重试 | 初次连接失败继续重试并计数 | 千台开局是连接风暴，避免把瞬时拥塞误判为永久离线 |
| 压测位置 | 大并发压测在容器网内跑（Rancher 宿主转发上限 ≈185 连接/端口） | 本机限制 |

### 4.6 安全基线自检（`security-check`）

六项可重复执行：① TLS+正确凭证连通 ② 匿名拒 ③ 错密码拒 ④ 合法设备发他人 topic 拒且断开 ⑤ 明文打 8883 失败 ⑥ 明文 1883 dev 形态回归通过。
**判据意义**：任一不过 → 公网路径未达基线，不得开放 8883。

---

## 5. 全参数表

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

**期望输出与端到端示例**：见《示例集》§5~§6（含实测输出）。

## 6. 设计要点与不变量

| 要点 | 说明 |
|---|---|
| 工具不进生产 | 独立模块，不参与部署；与生产代码只共享契约 |
| 两身份形态 | dev（`dev-{VIN}` 匿名明文）↔ 生产（`clientid=username=VIN` + TLS），由 `internal/simconn` 统一 |
| 造坏数据 | 刻意注入欠压/高温/故障/能量回收，让告警与清洗链路有真实样本 |
| 对拍机制 | `simframe` 造帧器与 codec 解码器**独立实现同一规格**，黄金样本双端各存一份 |
| 设计出处 | 《接入层设计》§10.1（模拟与验证方案）；帧规格《GB32960 映射》§5/§5.1/§5.2 |

## 7. 目录

```text
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

## 8. 延伸阅读（为什么这么设计）

- （《接入层设计》§8.3）

> 本手册只讲"怎么跑/怎么验"；上面的层文档讲"为什么"。设计与规格的权威在那两篇，本手册不复制其内容。
