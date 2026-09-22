# examples —— 方法与接口阶段完整示例

验证环境：Go 1.22.2（darwin/arm64）。

运行方式：本目录每个文件都是**独立的 `package main` 入口**，用单文件模式运行（`go run <文件>.go`）。请勿在本目录执行 `go build ./...` / `go vet ./...`（同一目录多个 `main` 会冲突）。

| 文件 | 说明 | 运行 |
|------|------|------|
| `ex01-receiver.go` | 值接收者 vs 指针接收者：修改副本还是修改原值，字面量不可寻址 | `go run ex01-receiver.go` |
| `ex02-sensor.go` | Sensor 小接口 + 隐式实现：CAN（值接收者）/ UART（指针接收者）统一采集 | `go run ex02-sensor.go` |
| `ex03-storage-todo.go` | Storage 接口由使用方定义：TodoService 依赖接口而非具体存储 | `go run ex03-storage-todo.go` |
| `ex04-nil-interface.go` | nil 接口陷阱：接口值 =（类型, 数据指针），持有 nil 指针的接口非 nil | `go run ex04-nil-interface.go` |
| `ex05-type-switch.go` | 类型断言与 type switch：ok 模式不 panic，按具体类型分发数据 | `go run ex05-type-switch.go` |

五个示例均已通过 `gofmt -l`（零差异）、`go vet`（零报告）、`go run`（行为符合预期），验证状态：已验证（Go 1.22.2）。
