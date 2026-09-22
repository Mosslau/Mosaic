// 来源：ph15-version-toolchain 练习 1 参考实现（sol-01-workspace）——app 模块
// 一句话说明：练习 1 的完整答案 = 本 sol 目录下三个文件（go.work + lib/ + app/）。
// 先自己在别处从零建一遍：go mod init 两个模块 → go work init ./app ./lib →
// app import lib → go run ./app 跑通，再对照本目录。
//
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 运行（cd sol-01-workspace，go.work 所在处）：
//
//	go run ./app                          # 输出 Hello, world! (lib v0.0.0-workspace)
//	go test ./app/... ./lib/...           # workspace 双模块全测
//	go env GOWORK                         # 打印 go.work 绝对路径（workspace 生效证明）
//	go list -m -json tenetlang/go/ph15-version-toolchain/exercises/sol-01-workspace/lib
//	                                      # Main:true + Dir=本地目录
//
// 验证块（go1.25.6 实测，2026-09-02，命令在 sol-01-workspace 根执行）：
//
//	$ go run ./app
//	Hello, world! (lib v0.0.0-workspace)
//	$ go test ./app/... ./lib/...
//	ok  	tenetlang/go/ph15-version-toolchain/exercises/sol-01-workspace/app	0.006s
//	ok  	tenetlang/go/ph15-version-toolchain/exercises/sol-01-workspace/lib	0.006s
//	$ go vet ./app/... ./lib/... && go test -race ./app/... ./lib/...
//	（vet 零输出；race 两包 ok，无数据竞争报告）
//	$ go env GOWORK
//	…/languages/go/ph15-version-toolchain/exercises/sol-01-workspace/go.work
//	$ go list -m -json tenetlang/go/ph15-version-toolchain/exercises/sol-01-workspace/lib | head -3
//	{ "Path": "tenetlang/go/ph15-version-toolchain/exercises/sol-01-workspace/lib",
//	  "Main": true,
//	  "Dir": "…/exercises/sol-01-workspace/lib" }
//	（Main:true = 该模块由 workspace 提供，来自本地目录而非 proxy；相对路径
//	./lib 不能直接传给 go list -m，需完整模块路径——go1.25.6 实测）
package main

import (
	"fmt"
	"os"

	"tenetlang/go/ph15-version-toolchain/exercises/sol-01-workspace/lib"
)

func run(name string) string {
	return lib.Hello(name)
}

func main() {
	name := "world"
	if len(os.Args) > 1 {
		name = os.Args[1]
	}
	fmt.Println(run(name))
}
