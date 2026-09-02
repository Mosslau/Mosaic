// 来源：ph15-version-toolchain 练习 2 参考实现（sol-02-upgrade）——库 v1.1.0
// 一句话说明：v1.1.0"升级"了默认问候语（开发团队自认为只是措辞优化）。
// 教学点：语义化版本承诺 API 兼容，但不承诺"可观察行为不变"——升级到 v1.1.0
// 后 Greet 输出从 "Hello, X!" 变成 "Hey, X!"，不改签名也破坏了消费者契约，
// 必须由消费者的测试验证（"依赖升级需要测试验证"）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 验证状态：已验证（go1.25.6，2026-09-02）
package greet

import "fmt"

// Greet 返回口语化问候语（v1.1.0 行为：以 "Hey, " 开头）。
func Greet(name string) string { return fmt.Sprintf("Hey, %s!", name) }
