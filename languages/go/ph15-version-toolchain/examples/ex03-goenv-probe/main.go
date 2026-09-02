// 来源：ph15-version-toolchain 示例 3 —— go env 语义探测
// 一句话说明：go env 输出的是"go 命令看到的环境"（默认值 + 配置文件 + 环境变量
// 覆盖后的最终值）。本程序调用 `go env -json` 拉取关键键并逐条注解语义——
// 重点区分 GOROOT（工具链安装目录）、GOPATH（工作区根）、GOMODCACHE（模块
// 源码缓存）与 GOCACHE（编译产物缓存）四类路径。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方 + 本机 go 命令
// 运行：
//
//	go test -v ./...
//	go vet ./...
//	go run .
//
// 验证状态：已验证（go1.25.6，2026-09-02）
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
)

// keys 需要探测并注解的键。
var keys = []string{
	"GOROOT", "GOPATH", "GOMODCACHE", "GOCACHE", "GOBIN",
	"GOTOOLCHAIN", "GOVERSION", "GOOS", "GOARCH", "GOPROXY", "GOSUMDB", "GOWORK",
}

// probe 调用 `go env -json <keys...>`，返回 key → value 映射。
func probe() (map[string]string, error) {
	args := append([]string{"env", "-json"}, keys...)
	out, err := exec.Command("go", args...).Output()
	if err != nil {
		return nil, fmt.Errorf("go env: %w", err)
	}
	m := map[string]string{}
	if err := json.Unmarshal(out, &m); err != nil {
		return nil, fmt.Errorf("解析 go env -json 输出: %w", err)
	}
	return m, nil
}

// describe 返回每个键的一句话语义（纯函数，供 main 与测试共用）。
func describe(key string) string {
	switch key {
	case "GOROOT":
		return "工具链安装目录（go 命令、编译器所在；runtime.GOROOT 等价）"
	case "GOPATH":
		return "工作区根（默认 ~/go）；module 模式下是 GOMODCACHE/GOBIN 的宿主"
	case "GOMODCACHE":
		return "模块缓存：go mod download 的 zip 与解压源码落点（默认 $GOPATH/pkg/mod）"
	case "GOCACHE":
		return "构建缓存：编译中间产物（内容寻址，可随时删，go clean -cache）"
	case "GOBIN":
		return "go install 的二进制安装目录（默认 $GOPATH/bin；空 = 用默认）"
	case "GOTOOLCHAIN":
		return "工具链选择策略：auto（默认，按需下载）/ local / path / 指定 goX.Y.Z"
	case "GOVERSION":
		return "当前 go 命令的版本号（如 go1.25.6）"
	case "GOOS":
		return "目标操作系统（交叉编译时改这里）"
	case "GOARCH":
		return "目标 CPU 架构（交叉编译时改这里）"
	case "GOPROXY":
		return "模块代理地址（默认 proxy.golang.org,direct；可 file:// 离线代理）"
	case "GOSUMDB":
		return "模块校验和数据库（go.sum 的信任根；off 关闭校验）"
	case "GOWORK":
		return "当前生效的 go.work 路径（非空 = 处于 workspace 中）"
	}
	return ""
}

func main() {
	env, err := probe()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println("=== go env 关键项（go1.25.6 实测）===")
	for _, k := range keys {
		fmt.Printf("%-12s = %-38s  ← %s\n", k, quote(env[k]), describe(k))
	}
}

func quote(v string) string {
	if v == "" {
		return "(空)"
	}
	return v
}
