# examples —— 标准库阶段完整示例

验证环境：Go 1.22.2（darwin/arm64），仅标准库，无第三方依赖。

运行方式：五个示例各自是**独立的 Go module**（目录内自带 go.mod），请先进入示例目录再运行——请勿在 examples/ 根目录执行 `go build ./...`（根目录没有 go.mod）。

| 目录 | 说明 | 运行 |
|------|------|------|
| `ex01-file-stats/` | 文件统计工具：bufio.Scanner 逐行统计行数/单词数，流式处理不占内存 | `cd ex01-file-stats && go run . <文件路径>` |
| `ex02-json-config/` | JSON 配置解析器：结构体 tag + os.ReadFile + json.Unmarshal + 业务校验 | `cd ex02-json-config && go run . demo.json` |
| `ex03-http-api/` | HTTP API server：net/http 路由 + json.NewEncoder 响应 + 显式超时 | `cd ex03-http-api && go run .`，另开终端 `curl http://127.0.0.1:8080/devices/car-001` |
| `ex04-todo-cli/` | 命令行 Todo 工具：flag 解析 + JSON 文件持久化（MarshalIndent） | `cd ex04-todo-cli && go run . -add "写周报"`、`go run . -list` |
| `ex05-wordcount-test/` | 单元测试：testing + 表驱动测试 + t.Run 子测试 | `cd ex05-wordcount-test && go test -v` |

五个示例均已通过 `gofmt -l`（零差异）、`go vet ./...`（零报告）、`go run`/`go test`（行为符合预期），验证状态：已验证（Go 1.22.2）。
