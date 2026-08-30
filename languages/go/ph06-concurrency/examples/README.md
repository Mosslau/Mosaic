# examples —— 并发编程阶段完整示例

验证环境：Go 1.22.2（darwin/arm64），仅标准库，无第三方依赖。

运行方式：五个示例各自是**独立的 Go module**（目录内自带 go.mod），请先进入示例目录再运行——请勿在 examples/ 根目录执行 `go build ./...`（根目录没有 go.mod）。

| 目录 | 说明 | 运行 |
|------|------|------|
| `ex01-waitgroup-sum/` | goroutine + WaitGroup 并发求和，分段写入不同槽位无锁安全 | `cd ex01-waitgroup-sum && go run .` |
| `ex02-unbuffered-channel/` | 无缓冲 channel 的配对同步：worker 完成后向 main 交接信号 | `cd ex02-unbuffered-channel && go run .` |
| `ex03-select-timeout/` | select + time.After 超时控制：并发抓取两数据源，超时先降级 | `cd ex03-select-timeout && go run .` |
| `ex04-worker-pool/` | worker pool 任务队列 + context 取消：worker 与派发方都监听 `ctx.Done()` | `cd ex04-worker-pool && go run .` |
| `ex05-race-counter/` | 数据竞争演示：`bad/` 无锁版必现 DATA RACE，`good/` Mutex 版无警告 | `cd ex05-race-counter && go run -race ./bad` 与 `go run -race ./good` |

> **说明**：示例 5 必须用 `go run -race` 运行——`-race` 是数据竞争的必用验收工具（见主文档 4.4 节）；`bad/` 无锁版仅用于演示数据竞争，切勿直接当正确代码使用。

五个示例均已通过 `gofmt -l`（零差异）、`go vet ./...`（零报告）、`go run`（行为符合预期），验证状态：已验证（Go 1.22.2）。
