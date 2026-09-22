// 来源：ph20-config-release examples/ex04-version-injection/version.go
// 一句话说明：构建版本信息注入的两种载体——ldflags -X 注入的语义版本，
// 与 runtime/debug.ReadBuildInfo 自动带上的 Go/VCS 信息。运行期的版本自报
// 是"快速定位运行版本"（roadmap 阶段验收 2）的唯一可靠入口（主文档 3.5）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行（dev 版）：go run .
// 带注入构建：go build -ldflags "-X main.version=v1.2.3 -X main.commit=9f1a2b3 -X main.date=2026-09-03T00:00:00Z" -o /tmp/ph20-ex04 .
//
//	/tmp/ph20-ex04    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"fmt"
	"runtime"
	"runtime/debug"
)

// 以下三个变量是 ldflags -X 的注入点：默认值让"未注入"的构建（go run / go build
// 不带 ldflags）也能跑，并诚实显示 dev。版本号本身（v1.2.3 这类）应该由发布流水线
// 依据 git tag / commit 生成后传入——绝不手工改这几个默认值当"发版"。
var (
	version = "dev"     // 语义版本（ldflags: -X main.version=v1.2.3）
	commit  = "none"    // 提交短哈希（ldflags: -X main.commit=9f1a2b3）
	date    = "unknown" // 构建时间（ldflags: -X main.date=2026-09-03T00:00:00Z）
)

// Info 是版本自报的完整视图：注入值 + Go 运行时 + 模块 + VCS 信息。
type Info struct {
	Version     string // ldflags 注入的语义版本；未注入为 "dev"
	Commit      string // ldflags 注入的提交号；未注入为 "none"
	Date        string // ldflags 注入的构建时间；未注入为 "unknown"
	GoVersion   string // 编译它的 Go 版本（runtime.Version()）
	OSArch      string // GOOS/GOARCH
	ModulePath  string // 主模块路径（ReadBuildInfo）
	VCSRevision string // git revision（ReadBuildInfo 的 settings，由 go 命令自动带）
	VCSTime     string // git 提交时间
}

// Gather 收集版本信息。ReadBuildInfo 在 go build / go run 产物的元数据里都可用；
// 它的 vcs.revision/vcs.time 是 go 命令构建时从所在 git 仓库自动读取的——
// 即使忘了传 ldflags，至少还能定位到代码版本（发布排障的兜底层）。
func Gather() Info {
	info := Info{
		Version: version,
		Commit:  commit,
		Date:    date,
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

// Summary 输出一行短摘要（适合日志启动行 / /version 端点）。
func (i Info) Summary() string {
	return fmt.Sprintf("version=%s commit=%s go=%s build=%s (%s)",
		i.Version, i.Commit, i.GoVersion, i.Date, i.OSArch)
}

// Full 输出完整视图，对齐排版便于人读。
func (i Info) Full() string {
	return fmt.Sprintf(`version:      %s
commit:       %s
build date:   %s
go version:   %s
os/arch:      %s
module:       %s
vcs revision: %s
vcs time:     %s`,
		i.Version, i.Commit, i.Date, i.GoVersion, i.OSArch,
		i.ModulePath, i.VCSRevision, i.VCSTime)
}
