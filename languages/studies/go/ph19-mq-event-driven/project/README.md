# ph19 阶段项目：车辆遥测消费服务

## 需求

把 roadmap §19 推荐项目「车辆遥测消费服务」落地为消费链路里的"清洗 / 消费 / 存储"段：车辆侧产生的遥测事件被写入 `fleet.telemetry.v1` topic（本项目用确定性数据集模拟上游，真实上游是 ph21 的 MQTT/网关采集写入），本服务以消费者组形式拉取，兑现 ph17/ph18 埋下的上下文——**ph17 project 的扩展方向"把指令受理扩展为异步队列、管理面与投递链分离"、ph18 3.6 埋的"POST 靠 Idempotency-Key 兜底重试，届时演化为消费端幂等表的异步版本"、ph18 全篇预告的"事件 schema 需要版本管理"在这里逐一兑现**：

- **幂等消费**：每条事件带 `MsgID` 幂等键，投递层 at-least-once（数据集里放了 3 条同 MsgID 的重复投递），消费端用幂等窗口保证副作用只生效一次
- **schema 版本管理**：事件带 `schemaVersion` 信封；数据集含一条 `v9` 未来版本事件——消费者不猜语义，按毒消息进死信
- **重试与死信**：抖动车辆事件会先失败再成功（可见重试路径）；坏载荷与未知 schema 是毒消息、不重试立即进死信；重试耗尽另有分类
- **顺序性与并行度**：key=vehicleID 稳定散列分区 → 同车事件分区内有序（examples/ex05 语义），topic 多分区提供组内并行度
- **积压水位**：消费端记录"高水位 − 提交位置"的最大积压，终态必须归零（examples/ex06 语义）

## 功能清单

- [x] 内存 fake broker（Kafka 语义：N 分区有序日志、key 散列、高水位）——真 Kafka 切换点
- [x] 确定性数据集：5 辆正常车 ×6 条（含超速样本）+ 3 条重复投递 + 1 条抖动车 + 1 条坏载荷 + 1 条未来 schema
- [x] 消费循环：解码 → 幂等查重 → 有界重试处理 → 记账/死信 → 分区提交（内嵌接口定义在使用方：`consumer.Log`）
- [x] 每车快照落库（samples/overspeed/lastTS/lastSpeed）——重复投递不重复计数
- [x] 死信台账：reason 分类（decode / schema / exhausted）+ attempts
- [x] 积压观测：过程最大积压 MaxLag、终态归零校验
- [x] 消费报表 CLI 输出（cmd/telemetry-consumer）

## 目录结构

```
project/
├── go.mod                    # go 1.25.0（全仓语言版本档）
├── doc.go                    # module 根包（供根 e2e 测试挂载）
├── e2e_test.go               # 端到端验收：数据集输入 ↔ 消费结果逐项对账
├── cmd/telemetry-consumer/   # 组装点：topic + dataset → store/dedup/dlq → consumer → 报表
└── internal/
    ├── model/                # 遥测事件模型（schemaVersion 信封 + MsgID 幂等键）
    ├── broker/               # fake broker（Kafka 语义 topic；真 Kafka 的替换点）
    ├── store/                # 每车快照 + 有界幂等窗口 + 死信台账
    ├── process/              # 解码/schema 校验/落快照 + 毒消息分类哨兵（ErrDecode/ErrSchema）
    ├── consumer/             # 消费循环：幂等+重试+死信+lag（定义 Log/Processor 接口）
    └── dataset/              # 确定性数据集（离线录音回放）
```

依赖方向（单向向内，无环）：

```text
cmd/telemetry-consumer ──▶ consumer ──▶ process ──▶ store
        │                    │             └──────▶ model
        └──▶ broker/dataset   └──▶ model（Log 的返回类型）
```

## 验证环境与命令

- 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（只用标准库）；go 命令需带仓库统一重定位环境
  （`GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache GOPROXY=https://goproxy.cn,direct GOSUMDB=off`）
- 构建/测试/静态检查：`go build ./... && go test ./... && go vet ./...`（另推荐 `go test -race ./...`）
- 运行：`go run ./cmd/telemetry-consumer -partitions 4 -max-attempts 3`
- **验证状态：已验证**——go1.25.6 本机实测 vet/build/test 全绿、`go test -race ./...` 全绿、gofmt 合规；运行输出见下方预期

```text
== 车辆遥测消费服务：topic=4 分区，数据集 36 条 ==
== 消费报表 ==
   读取 36 条：真实生效 31，重复投递拦截 3，内部重试 1 次
   死信 2 条（毒消息 2 + 重试耗尽 0），最大积压 13 条
   （每车快照样例、死信台账明细略）
终态积压：0 条（应归零）
```

## 真 Kafka 切换

本仓库（macOS）无 Kafka broker 与 Docker，离线形态用 `internal/broker` 内嵌语义；在有 Kafka 的机器上切换如下（`consumer`/`process`/`store` 无需改动，因为消费端只依赖 `consumer.Log` 接口）：

```bash
# 1. 引入客户端库
go get github.com/segmentio/kafka-go@latest

# 2. 起本地 broker（有 Docker 时）
docker run -d --name kafka -p 9092:9092 apache/kafka:3.7.0
kafka-topics.sh --create --topic fleet.telemetry.v1 --partitions 4 --replication-factor 1 --bootstrap-server localhost:9092

# 3. 生产端：Writer{Topic: "fleet.telemetry.v1"}，按 key=vehicleID 写（保证同车同分区）
# 4. 消费端：ReaderConfig{GroupID: "fleet-consumers", Brokers: [...]}，
#    循环 ReadMessage → consumer 的 processOne 逻辑 → CommitOffsets
```

该真 broker 路径「未在本环境验证」（本机无 broker/Docker）；命令可复现，验证以你机器上的实际 broker 为准。

## 验收标准

- [ ] `go build ./... && go test ./... && go vet ./...` 通过（go1.25.6 本机实测通过（已验证））；`go test -race ./...` 通过
- [ ] e2e 测试全绿：消费结果与输入账本对账（applied=唯一事件数、重复投递全部拦截、死信按 decode/schema 分类、终态积压 0、MaxLag>0）
- [ ] 能指认"消费链路"四个语义各落在哪一行：幂等窗口（consumer.processOne → store.SeenWindow）、schema 版本校验（process.Process → model.SchemaV1）、毒消息/耗尽分类（process.ErrSchema/ErrDecode → dead reason）、积压水位（consumer.observeLag/MaxLag）
- [ ] 能说出真 Kafka 切换只改哪一层（internal/broker → kafka-go），以及为什么 consumer/process/store 不用动（接口定义在使用方）
- [ ] 做一个"破坏实验"：删掉 consumer 里 `dedup.Seen` 的查重分支 → e2e 中 applied 大于唯一事件数（重复投递二次生效），测试变红；还原后变绿——能解释这条防线的作用

## 扩展方向

- 把 `store.SeenWindow` 换成 Redis `SETNX` + TTL 或 DB 唯一约束，幂等表跨实例共享、可重启不丢（离线形态为进程内存）
- 把"内部重试"升级为 retry topic / 延迟队列（参考 exercises/sol-04），attempts 随消息流转，多实例可接管续算
- 真 outbox：把"落快照 + 记账"放进同一事务，消灭"效果与记账之间崩溃"的窗口期（主文档 3.9）
- 常驻消费 + HTTP/指标面：`GET /healthz`、`/metrics`（consumer_lag）——监控接线属 ph12 可观测性，积压水位语义见 examples/ex06
- 与 ph21 衔接：上游改为真实 MQTT 采集网关（写入端），本服务不变，消费链路闭合
