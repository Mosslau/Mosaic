// 来源：ph20-config-release exercises/sol-02-version-injection/version.go
// 一句话说明：练习 2 参考实现——把"构建版本信息注入"做成可复用的包级能力：
// ldflags -X 注入三个变量 + runtime/debug.ReadBuildInfo 兜底，并提供
// 文本/JSON 两种输出形态（/version 端点与运维 -version 复用同一数据）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 带注入构建：go build -ldflags "-X main.version=v1.4.0 -X main.commit=abc1234 -X main.date=2026-09-03T00:00:00Z" -o /tmp/ph20-sol02 .
//
//	/tmp/ph20-sol02 -version    验证状态：已验证
package main

import (
	"encoding/json"
	"fmt"
	"runtime"
	"runtime/debug"
)

// ldflags -X 注入点：默认值让未注入构建也能跑，并诚实显示 dev。
var (
	version = "dev"
	commit  = "none"
	date    = "unknown"
)

// Info 是版本信息聚合：注入值 + Go 运行时 + 模块 + VCS。
type Info struct {
	Version     string `json:"version"`
	Commit      string `json:"commit"`
	BuildDate   string `json:"buildDate"`
	GoVersion   string `json:"goVersion"`
	OSArch      string `json:"osArch"`
	ModulePath  string `json:"modulePath"`
	VCSRevision string `json:"vcsRevision,omitempty"`
	VCSTime     string `json:"vcsTime,omitempty"`
}

// Gather 收集版本信息。语义版本来自 ldflags；vcs.revision/vcs.time 由
// go 命令构建时从 git 自动写入 debug.ReadBuildInfo——两层互为兜底。
func Gather() Info {
	info := Info{
		Version:   version,
		Commit:    commit,
		BuildDate: date,
	}
	info.GoVersion = runtime.Version()
	info.OSArch = runtime.GOOS + "/" + runtime.GOARCH
	if bi, ok := debug.ReadBuildInfo(); ok {
		info.ModulePath = bi.Main.Path
		for _, s := range bi.Settings {
			switch s.Key {
			case "vcs.revision":
				info.VCSRevision = s.Value
			case "vcs.time":
				info.VCSTime = s.Value
			}
		}
	}
	return info
}

// Summary 单行摘要（启动日志、error 上下文里快速带版本）。
func (i Info) Summary() string {
	return fmt.Sprintf("version=%s commit=%s go=%s build=%s (%s)",
		i.Version, i.Commit, i.GoVersion, i.BuildDate, i.OSArch)
}

// JSON 输出 /version 端点用的稳定结构：字段名即接口契约，
// 发布后不许随便改名（与 ph18 的"响应字段只增不删"同一条纪律）。
func (i Info) JSON() string {
	b, err := json.MarshalIndent(i, "", "  ")
	if err != nil {
		return fmt.Sprintf(`{"error":%q}`, err)
	}
	return string(b)
}
