// 来源：ph15-version-toolchain 练习 1 参考实现（sol-01-workspace）——lib 模块
// 一句话说明：被 app 依赖的本地库。lib 从未发布过任何版本（go.mod 无 tag），
// 只有 go.work 把它纳入 use 列表后，app 才能 import 它——这就是"多模块
// workspace：不发布也能互相依赖"的最小形态。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 运行（cd sol-01-workspace）：
//
//	go run ./app
//	go test ./app/... ./lib/...
//
// 验证状态：已验证（go1.25.6，2026-09-02）
package lib

import "fmt"

// Hello 返回问候语，版本号 v0.0.0-workspace 说明"这不是发布版本，是本地目录"。
func Hello(name string) string {
	return fmt.Sprintf("Hello, %s! (lib v0.0.0-workspace)", name)
}
