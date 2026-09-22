// 来源：ph15-version-toolchain 练习 2 参考实现（sol-02-upgrade）——消费者 consumer
// 一句话说明：consumer 依赖 example.com/greet 并用 replace 指向本地 v1.0.0 目录
// （模拟"锁在 v1.0.0"）。完整升级演练见下方"验证块"：改 require 到 v1.1.0 +
// 换 replace 到 ../greet-v1.1.0 + go mod tidy 后，greet_test.go 的契约断言当场
// 拦截行为变化（"Hello, " → "Hey, "）——这就是"依赖升级需要测试验证"的实测。
//
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（replace 本地目录，离线可复现）
// 运行（cd sol-02-upgrade/consumer）：
//
//	go test ./... && go vet ./... && go test -race ./...   # 锁 v1.0.0 全绿
//	go run .                                               # Hello, service-a!
//
// 升级演练（在 /tmp 副本里执行，避免污染本目录 go.mod；下方为实测输出）：
//
//	# 状态 1：v1.0.0 锁定
//	$ go test ./... && go run .
//	ok  	tenetlang/go/ph15-version-toolchain/exercises/sol-02-upgrade/consumer	0.006s
//	Hello, service-a!
//	# 状态 2：升级声明到 v1.1.0，并把 replace 切到 v1.1.0 目录
//	$ go mod edit -require=example.com/greet@v1.1.0
//	$ go mod edit -replace=example.com/greet=../greet-v1.1.0
//	$ go mod tidy
//	$ grep -E "require|replace" go.mod
//	require example.com/greet v1.1.0
//	replace example.com/greet => ../greet-v1.1.0
//	# 状态 2：跑测试 → 契约测试失败（拦截行为变化）
//	$ go test ./... ; echo exit=$?
//	--- FAIL: TestGreetContract (0.00s)
//	    greet_test.go:16: greet.Greet() = "Hey, service-a!", want prefix "Hello, "
//	FAIL
//	exit=1
//	# 状态 3a：回滚（另一条出路）→ 全绿
//	$ go mod edit -require=example.com/greet@v1.0.0
//	$ go mod edit -replace=example.com/greet=../greet-v1.0.0
//	$ go mod tidy && go test ./...
//	ok  	tenetlang/go/ph15-version-toolchain/exercises/sol-02-upgrade/consumer	(cached)
//	# 状态 3b：适配新契约（断言改 "Hey, " 前缀）再升 v1.1.0 → 全绿
//	$ go test ./...
//	ok  	tenetlang/go/ph15-version-toolchain/exercises/sol-02-upgrade/consumer	0.005s
//
// 验证状态：已验证（go1.25.6，2026-09-02，演练在 /tmp/sol02-drill 副本实测）
package main

import (
	"fmt"

	"example.com/greet"
)

func main() {
	fmt.Println(greet.Greet("service-a"))
}
