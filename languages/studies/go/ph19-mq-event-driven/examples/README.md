# ph19 消息队列与事件驱动示例

> 六个示例覆盖本阶段"可运行"的知识点主干：消费者组与 offset 语义（ex01）→ 幂等消费与去重表（ex02）→ 重试与死信状态机（ex03）→ 事件 schema 版本管理（ex04）→ 分区顺序性保证（ex05）→ 积压水位与监控（ex06）。每个示例是自包含的独立 Go module，零第三方依赖，在 go1.25.6 上按文件头命令可复现（`go vet ./...`、`go build ./...`、`go test ./...`）。

| 示例 | 一句话说明 | 对应主文档 | 运行/测试命令（进入各自子目录） |
|------|-----------|-----------|------------------------------|
| ex01-consumer-group-semantics | 消费者组语义：分区分配无重叠无遗漏、组级 offset 提交让接管者续读、提交前崩溃必重放（at-least-once 的本相） | 3.1、3.3 | `go run .`；`go test ./...`（5 个语义测试） |
| ex02-idempotent-consumer | 幂等消费：有界去重表按 MsgID 挡重复投递、副作用只生效一次、诚实标注"效果与记账之间崩溃"的窗口期 | 3.5 | `go run .`；`go test ./...`（6 个幂等测试） |
| ex03-retry-deadletter | 重试/死信状态机：有界重试 + 退避、可重试错误与毒消息分类、次数耗尽进 DLQ、毒消息不浪费重试 | 3.6 | `go run .`；`go test ./...`（6 个状态机测试） |
| ex04-event-schema-versioning | 事件 schema 版本管理：schemaVersion 信封、老消费者读 v2 新事件无损、字段改名/删除是静默破坏、未知未来版本显式拒绝 | 3.8 | `go run .`；`go test ./...`（6 个演进纪律测试） |
| ex05-order-guarantee | 顺序性保证：稳定分区键保住同一实体内部顺序；轮询/易变键让同 key 散落分区、跨分区拼接后顺序被打乱 | 3.4 | `go run .`；`go test ./...`（5 个顺序测试） |
| ex06-backlog-watch | 积压水位监控：HW−committed=lag 的观测器、生产快于消费时爬升、停写后追平、阈值边沿触发告警 | 3.7 | `go run .`；`go test ./...`（5 个水位测试） |

## 验证说明

- 全部示例 go.mod 为 `go 1.25.0`，与仓库语言版本档一致；`go vet ./...`、`go build ./...`、`go test ./...` 三条命令在每个子目录内执行。
- 验证环境：go1.25.6（darwin/arm64）；GOCACHE/GOMODCACHE 重定位到 /tmp 临时目录（`GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache GOPROXY=https://goproxy.cn,direct GOSUMDB=off`）；零第三方依赖，可离线复现。
- **验证状态：已验证**——go1.25.6 本机实测：6 个模块 `go vet ./... && go build ./... && go test ./...` 全绿、gofmt 合规（`gofmt -l .` 无输出；详见各文件头）。
- **产物纪律**：本机无 Kafka/NATS/RabbitMQ broker 与 Docker，全部示例采用「内存假 broker / 协议语义模拟」的离线可测策略——用纯标准库 + 接口抽象把消费者组分配、幂等消费、重试/死信状态机、积压水位的**语义**做出来并测试钉死；真正连 broker 的客户端代码（segmentio/kafka-go、nats.go 等）不在本示例落地（命令与说明见 `exercises/README.md` 与 `project/README.md` 的"真 broker 切换"段落，均标注「未在本环境验证」）。若在示例目录内执行 `go build ./...` 生成了二进制，请删除或改用 `go build -o /tmp/<名字> .`，仓库不落二进制。
- 正确性自证设计：6 个示例全部带单元测试，单测通过即证明分配语义、幂等效果、状态机转移、schema 演进、顺序保证、水位计算各自符合预期。
