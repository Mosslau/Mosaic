# ph21 IoT / 车联网 / 嵌入式相关 Go 示例

> 六个示例覆盖本阶段"可运行"的知识点主干：自研最小 MQTT（ex01）→ 设备鉴权/重连/幂等上报（ex02）→ 自研最小 WebSocket + 设备影子（ex03）→ OTA 分批灰度（ex04）→ 边缘网关转发（ex05）→ 遥测平台最小闭环（ex06）。每个示例是自包含的独立 Go module，零第三方依赖，在 go1.25.6 上按文件头命令可复现（`go vet ./...`、`go build ./...`、`go test ./...`）。

| 示例 | 一句话说明 | 对应主文档 | 运行/测试命令（进入各自子目录） |
|------|-----------|-----------|------------------------------|
| ex01-mqtt-minimal | 自研最小 MQTT 3.1.1（QoS0 子集）：报文编解码、通配订阅路由、连接鉴权、心跳保活，127.0.0.1 真 TCP | 3.1、4.1 | `go run . -broker 127.0.0.1:18830`；`go test ./...`（13 个协议/集成测试） |
| ex02-device-reconnect-idempotent | 设备鉴权（HMAC 动态 token + 常量时间校验）、指数退避重连、seq 单调幂等上报 | 3.2、3.3 | `go run .`；`go test ./...`（9 个 auth/dedup/e2e/重连测试） |
| ex03-websocket-shadow | 自研最小 RFC 6455 WebSocket（帧/掩码/心跳）+ 设备影子推送 + 面板广播，127.0.0.1 真 TCP | 3.4、3.6、4.2 | `go run . -addr 127.0.0.1:18880`；`go test ./...`（9 个帧/影子/心跳测试） |
| ex04-ota-service | OTA 升级服务：固件 sha256 台账、分批灰度、进度追踪、回滚决策（确定性回放） | 3.10 | `go run .`；`go test ./...`（4 个台账/决策测试） |
| ex05-edge-gateway | 边缘网关：长度前缀切帧、本地聚合、有界断网缓存（spool）、ack 水位断点续传、补传 e2e | 3.5、3.11、4.3 | `go run .`；`go test ./...`（7 个切帧/聚合/spool/网关测试） |
| ex06-telemetry-platform | 遥测平台最小闭环：接入 → 清洗（分类死信）→ 时序存储/实时状态 → 告警 → Prometheus 文本指标与查询 | 3.7、3.8、3.9 | `go run .`；`go test ./...`（7 个清洗/存储/告警/指标/链路测试） |

## 验证说明

- 全部示例 go.mod 为 `go 1.25.0`，与仓库语言版本档一致；`go vet ./...`、`go build ./...`、`go test ./...` 三条命令在每个子目录内执行。
- 验证环境：go1.25.6（darwin/arm64）；GOCACHE/GOMODCACHE 重定位到 /tmp 临时目录（`GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache GOPROXY=off GOSUMDB=off`）；零第三方依赖，可离线复现。
- **验证状态：已验证**——go1.25.6 本机实测：6 个模块 `go vet ./... && go build ./... && go test ./...` 全绿、gofmt 合规（`gofmt -l .` 无输出）；其中 **ex01 是真 TCP（127.0.0.1）上跑通自研 MQTT 协议**（编解码/路由/鉴权/心跳），**ex03 是真 TCP（127.0.0.1）上跑通自研 RFC 6455 WebSocket**（握手/掩码帧/心跳/影子推送）；ex02/ex05 走真 HTTP（httptest/loopback），ex04/ex06 走纯逻辑与内存存储。
- **产物纪律**：全部构建产物写 /tmp（`go build -o /tmp/<名字> .`），仓库不落二进制；`gofmt -l .` 应无输出。
- 正确性自证设计：6 个示例全部带单元/集成测试（共 49 个用例），单测通过即证明 MQTT 报文语义、鉴权时间窗、幂等窗、WS 帧规则、OTA 决策、spool 水位、时序查询、指标文本各自符合预期。

## 真中间件路径（本机无 Docker/broker，均「未在本环境验证」，命令可复现）

```bash
# 1. 真 MQTT broker（Mosquitto）+ 真 paho 客户端（替代 ex01 的自研路径）
docker run -d -p 1883:1883 eclipse-mosquitto:2
go get github.com/eclipse/paho.mqtt.golang@latest
#    ex01 的订阅/发布/鉴权语义在 paho 上等价：只是换传输实现，语义不变

# 2. 真 Kafka（替代 ph19 已覆盖的 topic 语义，主文档 3.7 缓冲段）
docker run -d --name kafka -p 9092:9092 apache/kafka:3.7.0
go get github.com/segmentio/kafka-go@latest

# 3. 真 Redis（替代 ex06 StatusCache 的实时状态缓存语义）
docker run -d -p 6379:6379 redis:7
go get github.com/redis/go-redis/v9@latest

# 4. 真时序库（替代 ex06 TSStore 的教学形态）
docker run -d -p 8086:8086 influxdb:2.7
go get github.com/influxdata/influxdb-client-go/v2@latest

# 5. 真 Prometheus 抓取 /metrics：把对应端点的文本格式喂给 Prometheus scrape 即可
```

以上路径的客户端形态与语义在本仓库离线示例中均以纯标准库实现并测试钉住；接真中间件时只需替换传输层/存储层，业务逻辑（3.1~3.11 的心智模型）不变。
