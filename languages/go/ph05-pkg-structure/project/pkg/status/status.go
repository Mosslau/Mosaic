// 来源：project/ —— 标准 Go 项目模板 pkg 公共库
// 一句话说明：pkg/status 设备状态常量与合法性校验，被 internal/device 引用（pkg 可被模块内任意包引用）。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：cd project && go run ./cmd/device-cli -selfcheck
// 验证状态：已验证（Go 1.22.2）
package status

// 设备状态常量——用命名常量替代魔术字符串
const (
	Online  = "online"
	Offline = "offline"
	Fault   = "fault"
)

// Valid 判断状态是否合法
func Valid(s string) bool {
	switch s {
	case Online, Offline, Fault:
		return true
	}
	return false
}
