# ph02 函数与错误处理 示例

> 每个示例是主文档第 6 章对应示例的完整可运行版。验证环境：Go 1.22.2（darwin/arm64），无外部依赖。

| 文件 | 说明 | 运行 |
|------|------|------|
| ex01-safe-divide.go | 安全除法：多返回值与 errors.New | `go run ex01-safe-divide.go` |
| ex02-read-file-defer.go | 文件读取：defer 关闭文件、%w 包装错误 | `go run ex02-read-file-defer.go` |
| ex03-config-errors-is.go | 配置解析：哨兵错误 + errors.Is 判定 | `go run ex03-config-errors-is.go` |
| ex04-cli-validator.go | 参数校验：函数类型、闭包、可变参数、错误聚合 | `go run ex04-cli-validator.go` |
| ex05-panic-recover.go | panic/recover 边界：顶层捕获转为 error | `go run ex05-panic-recover.go` |

每个文件都是独立的 package main，单独 `go run` 即可（同一目录下多个 main 函数不能一起 `go build ./...`，请逐文件运行）。

全部已在本环境验证：`gofmt -l` 无差异、`go vet` 通过、`go run` 输出符合预期（Go 1.22.2）。
