// 来源：ph21-iot-vehicle-edge project/internal/version/version.go
// 一句话说明：版本/构建信息注入点（-ldflags -X，主文档 ph20 3.6 机制复用）。
// 默认值是诚实探针：未走发布流水线的构建一眼可辨。
package version

var (
	// Version 语义版本，构建时 -ldflags "-X .../internal/version.Version=v1.2.3" 注入。
	Version = "dev"
	// Commit git 提交号。
	Commit = "none"
	// BuildTime 构建时间。
	BuildTime = "unknown"
)
