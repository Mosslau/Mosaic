// 来源：ph15-version-toolchain 练习 2 参考实现（sol-02-upgrade）——库 v1.0.0
// 一句话说明：example.com/greet 的 v1.0.0 源码（本地目录，由 replace 映射）。
// 契约：Greet(name) 以 "Hello, " 开头。v1.1.0（见 ../greet-v1.1.0）改了默认
// 问候语——升级时消费者的契约测试会拦截，见 consumer/greet_test.go。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 运行（cd sol-02-upgrade/consumer）：go test ./... && go run .
// 验证状态：已验证（go1.25.6，2026-09-02）
package greet

import "fmt"

// Greet 返回标准问候语（v1.0.0 契约：以 "Hello, " 开头）。
func Greet(name string) string { return fmt.Sprintf("Hello, %s!", name) }
