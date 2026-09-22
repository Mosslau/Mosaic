# ph01 基础语法 示例

> 每个示例是主文档 `01-basic-syntax.md` 第 6 章对应示例的完整可运行版。验证环境：Go 1.22.2 darwin/arm64（建议 Go 1.21+）。

| 文件 | 说明 | 运行 |
|------|------|------|
| ex01-calculator.go | 命令行计算器：读算式求值，处理除零 | `go run ex01-calculator.go`（然后输入如 `3 + 4` 回车） |
| ex02-word-frequency.go | 词频统计：用 map 统计单词出现次数 | `go run ex02-word-frequency.go` |
| ex03-is-prime.go | 判断素数：打印 1~100 内全部素数 | `go run ex03-is-prime.go` |
| ex04-todo-cli.go | Todo CLI 最小版：slice 增、列、删待办 | `go run ex04-todo-cli.go` |

验证状态：全部已在本环境（Go 1.22.2）用 `go vet` + `go run` 验证通过，`gofmt -l` 无差异。每个文件都是独立的 `package main`，单文件即可 `go run`；如需编译为可执行文件，用 `go build ex0X-*.go`。注意 ex02 词频统计的输出顺序随机（map 遍历无序），属预期行为。
