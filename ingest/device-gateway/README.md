# device-gateway 车端接入网关

> OceanVerse 第 1 阶段第 2 步 —— 平台的数据"国门"
> 职责: 设备鉴权 → 限流 → 协议解析/校验 → 写 Kafka → 全程可观测
> 原则: 网关无业务逻辑、无状态、不直连数据库; 越"笨"越稳。
> 📐 设计文档（含成熟度评估）：《docs/接入层与车端接入网关设计-v1.md》

## 处理链与端口

```
通道一(设备直连 HTTP):
  车端设备/模拟器 ──POST /api/v1/vehicle/report──► metrics → auth(token) → ratelimit(全局+单设备) → handler(校验) ──┐
                                                                                                                   ├─► Kafka 异步批量写入
通道二(EMQX webhook):                                                                                              │   (VIN 哈希保序)
  车端设备 ──MQTT──► EMQX ──规则引擎 webhook──► POST /api/v1/mqtt/ingest: metrics → handler(验webhook密钥→校验) ──┘
```

| 端点 | 说明 |
|---|---|
| `POST /api/v1/vehicle/report` | 车端上报(通道一: 设备直连 HTTP) |
| `POST /api/v1/mqtt/ingest` | 车端上报(通道二: EMQX 规则引擎 webhook, 密钥头 `X-Webhook-Token`) |
| `GET /health` | 健康探针 |
| `GET /metrics` | Prometheus 指标 |
| `GET /debug/pprof/*` | 性能剖析 |

> 接入层整体设计(EMQX 链路/四支柱/生产加固清单)见 `ingest/README.md`

## 配置（全部走环境变量）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `GATEWAY_PORT` | `8080` | HTTP 端口 |
| `KAFKA_BROKERS` | `localhost:19092` | Kafka 地址(逗号分隔) |
| `KAFKA_TOPIC` | `vehicle-report-raw` | 车端数据 topic |
| `DEVICE_TOKENS` | `demo-token-001` | 设备令牌白名单(逗号分隔) |
| `GATEWAY_WEBHOOK_TOKEN` | `dev-webhook-secret` | EMQX webhook 来源密钥, 须与 emqx.conf 一致 |
| `GATEWAY_DEV_MODE` | `false` | ⚠️ 开发模式: 放行所有 `dev-` 前缀 token, 生产必须关 |
| `RATE_PER_DEVICE` | `10` | 单设备限流(条/秒) |
| `RATE_GLOBAL` | `5000` | 全局限流(条/秒) |
| `GATEWAY_READ_TIMEOUT` / `GATEWAY_WRITE_TIMEOUT` | `5s` | HTTP 超时 |
| `GATEWAY_SHUTDOWN_GRACE` | `10s` | 优雅退出宽限 |

## 前置：Go 模块代理（国内必配）

```bash
go env -w GOPROXY=https://goproxy.cn,direct
```

## 本地运行

```bash
# 0. 基础设施已就绪(deploy/README.md), Kafka 在 localhost:19092
cd ingest/device-gateway

# 1. 下载依赖 + 编译验证
go mod tidy
go build ./...
go vet ./...

# 1.5 单元测试(五包 30+ 用例: 契约校验/鉴权/限流/双通道 handler/配置)
go test ./... -count=1          # 全部通过
go test ./... -cover            # auth 100% / ratelimit 85% / config 84% / handler 77% / model 69%

# 2. 开发模式启动(允许 dev- 前缀 token, 方便联调压测)
GATEWAY_DEV_MODE=true go run ./cmd/server
```

启动日志应看到：`车端接入网关启动 port=8080 topic=vehicle-report-raw ...`

## 验证（另开终端）

### ① 正常上报 → Kafka 消费到

```bash
# 发一条(dev 模式)
curl -i -X POST http://localhost:8080/api/v1/vehicle/report \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: dev-OV20260001" \
  -d '{"vin":"OV20260001","ts":'"$(date +%s)"',"type":"vehicle_status",
       "data":{"speed":32.5,"soc":78,"voltage":60.2,"current":-5.1,
               "temp_max":35.0,"lng":113.94,"lat":22.54}}'
# 期望: HTTP 202 {"code":0,"message":"accepted"}

# Kafka 里应消费到(Kafka 自动建 topic)
docker exec ov-kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic vehicle-report-raw \
  --from-beginning --timeout-ms 5000
```

### ② 鉴权拦截（关 dev 模式重启后）

```bash
# 不带 token → 401
curl -i -X POST http://localhost:8080/api/v1/vehicle/report -d '{}'
# 期望: {"code":"UNAUTHORIZED",...}
```

### ③ 校验拦截

```bash
# soc=300 超出范围 → 400 INVALID_DATA
curl -X POST http://localhost:8080/api/v1/vehicle/report \
  -H "X-Device-Token: dev-x" \
  -d '{"vin":"OV20260001","ts":'"$(date +%s)"',"type":"vehicle_status","data":{"soc":300}}'
```

### ④ 指标

```bash
curl -s http://localhost:8080/metrics | grep gateway_requests_total
curl -s http://localhost:8080/metrics | grep gateway_kafka_write_total
```

## 压测

```bash
# 1 万设备、每台 5 秒一条(≈2000 QPS)、跑 60 秒
go run ./cmd/simulator -devices 10000 -interval 5s -duration 60s

# 10 万设备(≈2 万 QPS) —— 注意本机 fd 限制, 必要时 ulimit -n 1000000
go run ./cmd/simulator -devices 100000 -interval 5s -duration 120s
```

压测时观察：

```bash
# 网关处理速率/结果分布
curl -s http://localhost:8080/metrics | grep -E 'requests_total|inflight'
# pprof 性能剖析(压测进行中抓取 30s CPU profile)
go tool pprof http://localhost:8080/debug/pprof/profile?seconds=30
```

## MQTT 通道验证（企业级链路：设备 → EMQX → 规则引擎 → 网关 → Kafka）

```bash
# 0. 确认 EMQX 已启动(deploy/README.md), Dashboard: http://localhost:18083 (admin/public)
#    规则引擎应在 集成 → 规则 中看到 "ov_vehicle_ingress" 及其 webhook 动作

# 1. 启动网关(确保 webhook token 与 deploy/emqx/emqx.conf 中一致)
GATEWAY_DEV_MODE=true go run ./cmd/server

# 2. 用 MQTT 模拟器发数据(100 台车, 每台 5s 一条状态, 1% 概率带故障)
go run ./cmd/mqtt-simulator -broker tcp://localhost:1883 -devices 100 -interval 5s -duration 60s

# 3. Kafka 应消费到 MQTT 来源的消息(与 HTTP 通道同一个 topic)
docker exec ov-kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic vehicle-report-raw \
  --from-beginning --timeout-ms 10000

# 4. 观察按通道区分的指标
curl -s http://localhost:8080/metrics | grep 'gateway_requests_total'
# 应同时看到 path="/api/v1/vehicle/report" 和 path="/api/v1/mqtt/ingest" 两个标签

# 5. EMQX 侧观测: Dashboard → 客户端(应看到 100 个 dev-OV* 连接)
#    Dashboard → 集成 → 规则 → ov_vehicle_ingress(命中率/成功率)
```

## Docker 构建（可选，第 1 阶段后续上编排用）

```bash
docker build -t oceanverse/device-gateway:dev .
docker run --rm -p 8080:8080 \
  -e KAFKA_BROKERS=host.docker.internal:19092 \
  -e GATEWAY_DEV_MODE=true \
  oceanverse/device-gateway:dev
```

## 已知边界（刻意不做）

- 鉴权是静态白名单；第 2 阶段接车辆档案服务改为动态校验
- Kafka RequiredAcks=RequireOne 性能优先；要更强持久性改 `kafka.RequireAll`
- gRPC/TCP 私有协议通道后续在 `internal/` 下平级扩展（HTTP 与 MQTT 已实现）
- 消息清洗/字段加工不做（那是 Flink 计算层的职责）
