// Package version 聚合构建版本信息：ldflags -X 注入 + runtime/debug 兜底。
// 注入变量为包级导出 string，便于发布流水线用 -X 精确赋值：
//
//	go build -ldflags "-X tenetlang/go/ph20-config-release/project/internal/version.Version=v2.1.0 \
//	   -X tenetlang/go/ph20-config-release/project/internal/version.Commit=abc1234 \
//	   -X tenetlang/go/ph20-config-release/project/internal/version.BuildDate=2026-09-03T00:00:00Z"
//
// 未注入时默认 dev/none/unknown——诚实暴露"没走发布流水线"。
package version

import (
	"encoding/json"
	"fmt"
	"runtime"
	"runtime/debug"
)

// 注入点。注意：Go 工具链的 -X 只对包级 string 变量生效，且需完整 import 路径。
var (
	Version   = "dev"
	Commit    = "none"
	BuildDate = "unknown"
)

// Info 是版本视图（JSON 字段即 /version 接口契约，发布后不随便改名）。
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

// Gather 收集版本信息。vcs.* 由 go 命令构建时从 git 自动写入 ReadBuildInfo——
// 忘记传 ldflags 时仍能定位到"构建的是哪个提交"。
func Gather() Info {
	info := Info{Version: Version, Commit: Commit, BuildDate: BuildDate}
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

// Summary 单行摘要（启动日志）。
func (i Info) Summary() string {
	return fmt.Sprintf("version=%s commit=%s go=%s build=%s (%s)",
		i.Version, i.Commit, i.GoVersion, i.BuildDate, i.OSArch)
}

// JSON 输出 /version 端点载荷。
func (i Info) JSON() string {
	b, err := json.MarshalIndent(i, "", "  ")
	if err != nil {
		return fmt.Sprintf(`{"error":%q}`, err)
	}
	return string(b)
}
