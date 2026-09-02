// 来源：ph15-version-toolchain 练习 3 参考实现（sol-03-goreq）
// 一句话说明："记录项目 Go 版本要求"落成一个可执行检查：解析 go.mod 的
// module / go / toolchain 三行（go 行 = 语言版本与最小工具链门槛，toolchain 行 =
// 首选工具链），与当前编译它的工具链（runtime.Version()）比较，输出结论与
// 退出码——工具链版本"要求"被机器可读地记录并强制。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 运行（cd sol-03-goreq）：
//
//	go test -v ./... && go vet ./... && go test -race ./...
//	go run . -mod go.mod                          # 检查本模块自身（OK, exit 0）
//	go run . -mod testdata/gohigh.mod             # go 1.99.0 > 当前 → FAIL, exit 1
//	go run . -mod testdata/toolchain-new.mod      # toolchain go1.26.0 → WARN, exit 0
//
// 验证块（go1.25.6 实测，2026-09-02）：
//
//	$ go test -v ./... && go vet ./... && go test -race ./...
//	PASS / ok  	tenetlang/go/ph15-version-toolchain/exercises/sol-03-goreq	0.007s
//	（TestParseGoMod×5、TestCompareVersions×8、TestCheck×5 全 PASS；vet/race 零报告）
//	$ go run . -mod go.mod ; echo exit=$?
//	module   : tenetlang/go/ph15-version-toolchain/exercises/sol-03-goreq
//	go 行    : 1.25.0
//	toolchain: -（未声明）
//	当前工具链: 1.25.6（runtime.Version）
//	结论: OK —— 当前 1.25.6 ≥ go.mod 要求
//	exit=0
//	$ go run . -mod testdata/gohigh.mod ; echo exit=$?
//	结论: FAIL —— 当前 1.25.6 < go 行 1.99.0（硬门槛）
//	      GOTOOLCHAIN=auto 会尝试下载更新工具链；=local 会直接报错
//	exit=1
//	$ go run . -mod testdata/toolchain-new.mod ; echo exit=$?
//	结论: WARN —— go 行满足，但 toolchain 行 go1.26.0 > 当前 1.25.6
//	      auto 模式构建会下载并切换工具链；local 模式忽略该行（版本不统一风险）
//	exit=0
//
// 验证状态：已验证（go1.25.6，2026-09-02）
package main

import (
	"bufio"
	"fmt"
	"os"
	"runtime"
	"strconv"
	"strings"
)

// runtimeVersion 包装 runtime.Version()，便于测试替换。
var runtimeVersion = func() string { return runtime.Version() }

// Requirement 是从 go.mod 里解析出的版本要求。
type Requirement struct {
	Module    string // module 行
	Go        string // go 行（如 1.25.0）；缺失 = 未声明
	Toolchain string // toolchain 行（如 go1.25.6）；缺失 = 未声明
}

// parseGoMod 逐行解析 go.mod 的 module / go / toolchain 三行。
// 行首允许空白；跳过空行与 // 注释。未知指令忽略（不报错）。
func parseGoMod(data []byte) (*Requirement, error) {
	req := &Requirement{}
	sc := bufio.NewScanner(strings.NewReader(string(data)))
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "//") {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}
		switch fields[0] {
		case "module":
			req.Module = fields[1]
		case "go":
			req.Go = fields[1]
		case "toolchain":
			req.Toolchain = fields[1]
		}
	}
	return req, sc.Err()
}

// goVersion 去掉 "go" 前缀（toolchain 行形如 go1.25.6；go 行形如 1.25.0）。
func goVersion(v string) string { return strings.TrimPrefix(v, "go") }

// compareVersions 比较两个版本串（可带 go 前缀），按数字段比较、缺段补 0。
// 返回 -1 / 0 / 1。
func compareVersions(a, b string) int {
	as, bs := strings.Split(goVersion(a), "."), strings.Split(goVersion(b), ".")
	n := len(as)
	if len(bs) > n {
		n = len(bs)
	}
	for i := 0; i < n; i++ {
		av, bv := 0, 0
		if i < len(as) {
			av, _ = strconv.Atoi(as[i])
		}
		if i < len(bs) {
			bv, _ = strconv.Atoi(bs[i])
		}
		if av != bv {
			if av < bv {
				return -1
			}
			return 1
		}
	}
	return 0
}

// Check 输出检查结论；返回三态：ok / warn / fail（语义对齐 go 命令实测行为：
// go 行是硬门槛——当前工具链低于 go 行时构建必失败（GOTOOLCHAIN=auto 会尝试
// 下载更新、=local 直接报错）；toolchain 行是"首选"——高于当前时 auto 会下载
// 切换、local 会忽略该行继续构建，属团队需注意的告警而非硬错）。
func Check(req *Requirement, current string) (status string, lines []string) {
	lines = append(lines, fmt.Sprintf("module   : %s", req.Module))
	lines = append(lines, fmt.Sprintf("go 行    : %s", orDash(req.Go)))
	lines = append(lines, fmt.Sprintf("toolchain: %s", orDash(req.Toolchain)))
	lines = append(lines, fmt.Sprintf("当前工具链: %s（runtime.Version）", current))
	if req.Go == "" {
		lines = append(lines, "结论: go.mod 未声明 go 行，无强制要求（旧模块）")
		return "ok", lines
	}
	switch c := compareVersions(current, req.Go); {
	case c < 0:
		lines = append(lines, fmt.Sprintf("结论: FAIL —— 当前 %s < go 行 %s（硬门槛）", current, req.Go))
		lines = append(lines, "      GOTOOLCHAIN=auto 会尝试下载更新工具链；=local 会直接报错")
		return "fail", lines
	}
	if req.Toolchain != "" && compareVersions(current, req.Toolchain) < 0 {
		lines = append(lines, fmt.Sprintf("结论: WARN —— go 行满足，但 toolchain 行 %s > 当前 %s", req.Toolchain, current))
		lines = append(lines, "      auto 模式构建会下载并切换工具链；local 模式忽略该行（版本不统一风险）")
		return "warn", lines
	}
	lines = append(lines, fmt.Sprintf("结论: OK —— 当前 %s ≥ go.mod 要求", current))
	return "ok", lines
}

func orDash(s string) string {
	if s == "" {
		return "-（未声明）"
	}
	return s
}

func main() {
	modPath := "./go.mod"
	if len(os.Args) > 1 && os.Args[1] == "-mod" && len(os.Args) > 2 {
		modPath = os.Args[2]
	}
	data, err := os.ReadFile(modPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "读取 go.mod 失败:", err)
		os.Exit(2)
	}
	req, err := parseGoMod(data)
	if err != nil {
		fmt.Fprintln(os.Stderr, "解析 go.mod 失败:", err)
		os.Exit(2)
	}
	status, lines := Check(req, goVersion(runtimeVersion()))
	for _, l := range lines {
		fmt.Println(l)
	}
	if status == "fail" {
		os.Exit(1)
	}
}
