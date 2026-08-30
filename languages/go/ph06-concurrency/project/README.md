# 阶段项目：并发日志处理器

对应 roadmap ph06 推荐项目第一个「并发日志处理器」。多来源 goroutine 并发写入日志，channel 队列 + worker pool 消费，按级别过滤/聚合，超时刷新与优雅关闭——本阶段并发模型的完整落地。

## 需求

- `internal/logproc` 并发日志处理核心：
  - `Submit(ctx, Entry)` —— 多来源 goroutine 并发提交日志（有缓冲 channel 队列，天然线程安全）
  - worker pool 消费 —— 固定数量 worker 从 channel 取日志处理，控制并发度、复用 goroutine
  - 按级别过滤/聚合 —— 低于 `minLevel` 的条目丢弃并计数；按级别、来源累计输出条数
  - `FlushLoop(ctx, interval)` —— 周期刷新输出缓冲（超时刷新），日志不滞留
  - `Shutdown()` —— 优雅关闭：关闭输入队列 → 排空在途日志 → 刷出缓冲 → 等待全部 worker 退出
- `cmd/logd` 演示入口：3 个来源（collector / api / scheduler）并发写日志，输出过滤后的日志流与聚合统计

## 功能清单

| 功能 | 说明 |
|------|------|
| 并发写入 | channel 队列缓冲，多来源 `Submit` 无需加锁 |
| worker pool | 4 个 worker 并发消费（`New` 可配置数量） |
| 级别过滤 | DEBUG/INFO/WARN/ERROR 四级，低于 `minLevel` 丢弃并计入 `Filtered` |
| 级别/来源聚合 | 处理过程中按级别、来源累计条数，`Stats()` 输出 |
| 超时刷新 | ticker 周期 flush 输出缓冲 |
| 优雅关闭 | 停止接收 → 排空在途 → 刷出 → 退出，不丢日志 |
| 单元测试 | 级别过滤 / 在途排空 / 并发提交 3 组用例，`go test -race ./...` 无竞争 |

## 验收标准

- [ ] `gofmt -l .` 零差异、`go vet ./...` 零报告
- [ ] `go test ./...` 全部通过（级别过滤、在途排空、并发提交 3 个用例）
- [ ] `go test -race ./...` 无 DATA RACE
- [ ] `go run ./cmd/logd` 输出过滤后的日志流（2 条 DEBUG 被丢弃）+ 统计汇总：收到 11 条，丢弃 2 条，INFO 5 / WARN 2 / ERROR 2
- [ ] 代码符合 ph06 要点：发送方（来源）用 ctx 控制停止、发送方负责关闭（Shutdown）、无 goroutine 泄漏、显式 error

## 扩展方向

- 输出按来源分流到不同文件（fan-out 到多个 sink）
- 接入 `log/slog` 结构化日志（ph07 标准库阶段）
- 增加积压告警：worker 消费不过来时上报背压（ph08 测试与工程质量阶段可用 benchmark 压测）
- 用 `context.WithDeadline` 实现「最后一次强制刷新截止时间」
- 采集端与服务端分离、分布式部署（ph11 微服务与分布式阶段）

## 验证环境

- Go 1.22.2（darwin/arm64），无第三方依赖
- 运行命令：
  - `go run ./cmd/logd`
  - `go test ./...`
  - `go test -race ./...`
  - `go build ./...`
- 验证状态：已验证（Go 1.22.2）
