# examples —— 包管理与工程结构阶段完整示例

验证环境：Go 1.22.2（darwin/arm64），无第三方依赖。

运行方式：三个示例各自是**独立的 Go module**（ex03 还是多模块 workspace），请先进入示例目录再运行——请勿在 examples/ 根目录执行 `go build ./...`（根目录没有 go.mod）。

| 目录 | 说明 | 运行 |
|------|------|------|
| `ex01-todo-cli/` | 标准布局最小项目：cmd/todo 入口 + internal/todo 业务包，add/done/list/demo 命令 | `cd ex01-todo-cli && go run ./cmd/todo demo` |
| `ex02-vehicle-server/` | 设备接入语义标准布局：cmd + internal/vehicle + internal/canbus + internal/config 四包协作 | `cd ex02-vehicle-server && go run ./cmd/vehicle-server` |
| `ex03-workspace/` | 多模块 workspace：go.work 串联 lib/shared 共享库 + collector / reporter 两个服务 | `cd ex03-workspace && go run ./services/collector` |

> **说明**：ex03-workspace 的 collector / reporter 同时带 require + replace（示意脱离 workspace 时的替代路径）；有 go.work 时 workspace 优先，两者可并存。

三个示例均已通过 `gofmt -l`（零差异）、`go vet ./...`（零报告）、`go run`（行为符合预期），验证状态：已验证（Go 1.22.2）。
