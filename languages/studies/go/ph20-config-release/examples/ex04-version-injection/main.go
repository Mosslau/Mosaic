// 来源：ph20-config-release examples/ex04-version-injection/main.go
// 一句话说明：程序的自报版本打印。go run 未注入时显示 dev；
// 发布流水线用 ldflags -X 注入真实版本，二进制从此能回答"我是谁"（主文档 3.5）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import "fmt"

func main() {
	info := Gather()
	fmt.Println("== 完整版本视图 ==")
	fmt.Println(info.Full())
	fmt.Println()
	fmt.Println("== 一行摘要（启动日志 / version 端点用）==")
	fmt.Println(info.Summary())
	fmt.Println()
	fmt.Println("说明：语义版本来自 ldflags -X 注入（未注入显示 dev）；")
	fmt.Println("     vcs revision/time 由 go 命令构建时从 git 自动写入 ReadBuildInfo——")
	fmt.Println("     兜底定位「构建的是哪个提交」。")
}
