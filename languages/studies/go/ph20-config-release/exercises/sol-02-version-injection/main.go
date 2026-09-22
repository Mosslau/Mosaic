// 来源：ph20-config-release exercises/sol-02-version-injection/main.go
// 一句话说明：二进制入口——默认打印 JSON 版本；-version 简版单行（运维脚本用）。
// run 与 io 分离，让测试不真退出进程（主文档 3.5）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -version       验证状态：已验证
package main

import (
	"flag"
	"fmt"
	"io"
	"os"
)

// run 处理参数并写输出，返回进程退出码。逻辑与 os.Exit 分离便于测试。
func run(args []string, out io.Writer) int {
	fs := flag.NewFlagSet("app", flag.ContinueOnError)
	fs.SetOutput(out)
	versionFlag := fs.Bool("version", false, "print version and exit")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	info := Gather()
	if *versionFlag {
		fmt.Fprintln(out, info.Summary())
		return 0
	}
	fmt.Fprintln(out, info.JSON())
	return 0
}

func main() {
	os.Exit(run(os.Args[1:], os.Stdout))
}
