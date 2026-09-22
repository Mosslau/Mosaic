// 来源：ph15-version-toolchain 示例 4（ex04-workspace）主模块 service-a
// 一句话说明：service-a 是一个"服务"模块，import 同 workspace 的 sharedlib。
// 演示 workspace 的核心价值：service-a/go.mod 只 require sharedlib v0.0.0，
// go.work（use ./service-a ./sharedlib）把该模块路径解析到本地目录——改 sharedlib
// 源码后直接 go run 生效，无需先发布版本、无需 replace 行。本文件头之外的
// go.work 内容见 ex04-workspace/go.work。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 运行（cd examples/ex04-workspace，即 go.work 所在处）：
//
//	go run ./service-a
//	go test ./service-a/... ./sharedlib/... && go vet ./service-a/... ./sharedlib/...
//	go test -race ./service-a/... ./sharedlib/...
//	go env GOWORK        # 输出 go.work 绝对路径 = 证明 workspace 生效
//
// 注意：workspace 根目录用 ./... 会报 "does not contain modules listed in
// go.work"——多模块场景要用每个模块的目录 pattern（go 1.25.6 实测）。
// 验证状态：已验证（go1.25.6，2026-09-02）
package main

import (
	"fmt"

	"tenetlang/go/ph15-version-toolchain/examples/ex04-workspace/sharedlib"
)

// run 组装问候语；抽出来便于 main_test 直接断言（无需子进程）。
func run() string {
	return sharedlib.Greet("service-a")
}

func main() {
	fmt.Println(run())
}
