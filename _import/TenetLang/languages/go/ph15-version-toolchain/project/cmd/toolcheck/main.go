// 来源：ph15-version-toolchain 阶段项目（toolcheck）——CLI 入口
// 一句话说明：Go 工具链检查脚本（roadmap §15 推荐项目）。toolcheck 读取一个
// go.mod（-dir 向上查找或 -mod 直指），解析 module/go/toolchain 三行，与
// 当前工具链（runtime.Version()，即编译本程序的那个 go）对比，输出三态结论
// 与退出码：ok=0 / warn=0 / fail=1 / 用法或解析错误=2。可选 -want 施加
// 团队策略门槛，-json 输出结构化结果便于 CI 消费。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 运行（cd project）：
//
//	go test ./... && go vet ./... && go test -race ./...
//	go run ./cmd/toolcheck                    # 检查 project 自身 go.mod（OK）
//	go run ./cmd/toolcheck -mod ../exercises/sol-03-goreq/testdata/gohigh.mod
//	go run ./cmd/toolcheck -json -want go1.26.0
//
// 验证状态：已验证（go1.25.6，2026-09-02，实测输出见 project/README.md）
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"runtime"

	"tenetlang/go/ph15-version-toolchain/project/internal/check"
	"tenetlang/go/ph15-version-toolchain/project/internal/gomodfile"
)

func main() {
	dir := flag.String("dir", ".", "从该目录向上查找 go.mod")
	mod := flag.String("mod", "", "直接指定 go.mod 路径（优先于 -dir）")
	want := flag.String("want", "", "策略门槛：要求工具链 ≥ 该版本（如 go1.26.0 或 1.26.0）")
	asJSON := flag.Bool("json", false, "输出 JSON")
	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "用法: toolcheck [-dir DIR] [-mod FILE] [-want VERSION] [-json]\n")
		fmt.Fprintf(os.Stderr, "检查 go.mod 的 go/toolchain 行是否被当前工具链满足。\n")
		fmt.Fprintf(os.Stderr, "退出码: 0=满足/告警 1=不满足 2=用法或解析错误\n")
		flag.PrintDefaults()
	}
	flag.Parse()

	modPath := *mod
	if modPath == "" {
		p, err := gomodfile.FindUp(*dir)
		if err != nil {
			fmt.Fprintln(os.Stderr, "未找到 go.mod:", err)
			os.Exit(2)
		}
		modPath = p
	}
	req, err := gomodfile.ParseFile(modPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "读取 go.mod 失败:", err)
		os.Exit(2)
	}

	// 当前工具链 = 编译本程序的 go（runtime.Version()，形如 go1.25.6）
	r := check.Run(req, modPath, runtime.Version(), normalizeWant(*want))

	if *asJSON {
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		if err := enc.Encode(r); err != nil {
			fmt.Fprintln(os.Stderr, "JSON 输出失败:", err)
			os.Exit(2)
		}
	} else {
		fmt.Printf("go.mod    : %s\n", r.ModFile)
		fmt.Printf("module    : %s\n", r.Module)
		fmt.Printf("go 行     : %s\n", orDash(r.GoLine))
		fmt.Printf("toolchain : %s\n", orDash(r.Toolchain))
		fmt.Printf("当前工具链: %s（编译本程序的 go）\n", r.Current)
		if r.Want != "" {
			fmt.Printf("策略门槛  : %s\n", r.Want)
		}
		fmt.Printf("结论 [%s]: %s\n", r.Status, r.Message)
		if r.Details != "" {
			fmt.Printf("   %s\n", r.Details)
		}
	}

	switch r.Status {
	case check.StatusFail:
		os.Exit(1)
	case check.StatusOK, check.StatusWarn:
		os.Exit(0)
	default:
		os.Exit(2)
	}
}

// normalizeWant 允许 -want 传 "go1.26.0" 或 "1.26.0"，统一成 go 前缀形式。
func normalizeWant(w string) string {
	if w == "" {
		return ""
	}
	if len(w) >= 2 && w[:2] == "go" {
		return w
	}
	return "go" + w
}

func orDash(s string) string {
	if s == "" {
		return "-（未声明）"
	}
	return s
}
