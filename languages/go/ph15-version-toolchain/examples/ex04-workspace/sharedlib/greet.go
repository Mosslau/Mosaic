// 来源：ph15-version-toolchain 示例 4（ex04-workspace）共享库模块 sharedlib
// 一句话说明：这是 workspace 里被本地覆盖的"依赖方"——service-a 的 go.mod 只写
// require <sharedlib 模块路径> v0.0.0（v0.0.0 = "随便哪个版本，交给 go.work"），
// go.work 的 use 列表把该模块路径解析到本目录。没有 go.work 时 v0.0.0 无法从
// proxy 解析（本目录没有发布过任何版本），构建会失败——这正是 workspace 的用途：
// 多模块本地联调，不发布也能互相 import。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 运行（在 ex04-workspace 目录，即 go.work 所在处）：
//
//	go run ./service-a
//	go test ./service-a/... ./sharedlib/...   # workspace 双模块全测
//	go list -m -json ./sharedlib              # Main:true + Dir=本地目录
//
// 验证状态：已验证（go1.25.6，2026-09-02）
package sharedlib

import "fmt"

// Greet 返回问候语。workspace 场景下编译用的是本目录源码（未发布版本），
// 主模块 require 里写的 v0.0.0 只是占位。
func Greet(name string) string {
	return fmt.Sprintf("Hello from sharedlib, %s!", name)
}
