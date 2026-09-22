# ph17 架构设计与代码分层示例

> 四个示例覆盖本阶段"可运行"的知识点主干：三层骨架（ex01）→ 构造函数注入（ex02）→ 错误码与错误包装（ex03）→ 接口定义在使用方附近（ex04）。每个示例是自包含的独立 Go module，零第三方依赖，在 go1.25.6 上按文件头命令可复现（`go build ./...`、`go test ./...`、`go vet ./...`）。

| 示例 | 一句话说明 | 运行命令（进入各自子目录） |
|------|-----------|--------------------------|
| ex01-three-layer | 迷你 Todo 三层骨架：handler → service → store → domain 的职责分工与依赖方向，main 只做组装 | `go run . -addr 127.0.0.1:18081`，`curl http://127.0.0.1:18081/todos`；`go test ./...`（无测试文件，空跑通过） |
| ex02-constructor-injection | 手写构造函数注入 + 选项函数：Notifier 依赖 Sender 接口，渠道在 main 一处切换，测试塞 fakeSender | `go test ./...`（两个单测）；`go run . -sender sms` |
| ex03-error-code-wrap | 业务错误码（Code）与错误包装（*Error + Unwrap）：errors.Is 穿透根因、errors.As 取回 Code、HTTP 边界统一映射 {code,message} | `go test ./...`（三个单测）；`go run . -addr 127.0.0.1:18082` 后按 main.go 文件头 curl 冒烟 |
| ex04-interface-consumer | 消费方声明接口（report 包定义 ReportStore），提供方（sites 包）不 import 消费方；组装点 var _ 编译期断言；fake 替身注入 | `go run .`；`go test ./...`（两个单测） |

## 验证说明

- 全部示例 go.mod 为 `go 1.25.0`，与仓库语言版本档一致；`go build ./...`、`go test ./...`、`go vet ./...` 三条命令在每个子目录内执行。
- 验证环境：go1.25.6（darwin/arm64，Apple M4 Pro）；GOCACHE/GOMODCACHE 重定位到 /tmp 临时目录（`GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache GOPROXY=https://goproxy.cn,direct GOSUMDB=off`）；零第三方依赖，可离线复现。
- **验证状态：已验证**——go1.25.6 本机实测：4 个模块 `go build ./... && go test ./... && go vet ./...` 全绿、gofmt 合规（详见各文件头）。
- 正确性自证设计：ex02/ex03/ex04 均带单元测试（fake 替身、errors.Is/As 断言、httptest 映射断言），单测通过即证明注入与包装机制符合预期；ex01 无测试文件，`go test ./...` 空跑返回 0。
