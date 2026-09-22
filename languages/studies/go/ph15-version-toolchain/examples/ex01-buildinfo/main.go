// 来源：ph15-version-toolchain 示例 1 —— go version / 工具链版本嵌入（buildinfo）
// 一句话说明：演示"二进制里到底带了哪些版本信息"——runtime.Version() 是编译它的
// 工具链版本；debug.ReadBuildInfo() 给出模块路径、模块版本（来自 VCS tag 或
// -ldflags 注入）与 go 版本；在有 .git 的仓库里构建时还会自动盖 VCS 印章
// （vcs.revision / vcs.time / vcs.modified），即"可复现构建"的版本依据。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go vet ./...
//	go run .
//	go build -ldflags "-X main.version=v1.2.3" -o /tmp/ex01 . && /tmp/ex01
//	go version -m /tmp/ex01
//
// 验证状态：已验证（go1.25.6，2026-09-02）
package main

import (
	"fmt"
	"runtime"
	"runtime/debug"
)

// version 是构建期可注入的版本号：go build -ldflags "-X main.version=v1.2.3"
var version = "dev"

func main() {
	fmt.Print(report())
}

// report 打印本次构建的版本画像；测试用 reportString 断言结构。
func report() string {
	s := "runtime.Version(): " + runtime.Version() + "\n"
	s += "version var      : " + version + "\n"
	bi, ok := debug.ReadBuildInfo()
	if !ok {
		return s + "build info: unavailable\n"
	}
	s += fmt.Sprintf("main module      : %s %s\n", bi.Main.Path, bi.Main.Version)
	s += "go version(build): " + bi.GoVersion + "\n"
	for _, kv := range bi.Settings {
		switch kv.Key {
		case "vcs.revision", "vcs.time", "vcs.modified":
			s += fmt.Sprintf("setting %-13s: %s\n", kv.Key, kv.Value)
		}
	}
	return s
}
