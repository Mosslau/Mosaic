// 来源：ph17-architecture-layering project/internal/domain
// 一句话说明：领域包（依赖图最内层）。Device 的字段与状态是"业务词汇"，
// 全项目只有这里定义；handler/service/store 都引用它，它不引用任何人。
// 说明：本项目的"设备管理"只做 HTTP 管理面（注册/状态/固件/指令受理），
// 实时遥测与设备协议接入（MQTT/WebSocket 上行）属 ph21 IoT / 车联网 / 嵌入式相关 Go 阶段。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package domain

import (
	"errors"
	"time"
)

// Status 设备状态（管理面枚举）。
type Status string

const (
	StatusOnline      Status = "online"
	StatusOffline     Status = "offline"
	StatusMaintenance Status = "maintenance"
)

// ErrNotFound 是"数据不存在"的跨层语义：mem/file 两种存储实现都返回它，
// service 用 errors.Is 判断后翻译成业务错误码（见 internal/errs）。
// 放领域包而非某个存储包，是为了让 service 只依赖领域、不 import 具体实现。
var ErrNotFound = errors.New("device: not found")

// Device 车联网设备的管理面模型。
// json tag 为教学简化：响应直接序列化领域对象；更严格的 DTO 隔离见主文档 3.2。
type Device struct {
	ID       string    `json:"id"`
	Name     string    `json:"name"`
	Status   Status    `json:"status"`
	Firmware string    `json:"firmware"` // 语义化版本 major.minor.patch，空串 = 未安装
	LastSeen time.Time `json:"lastSeen"` // 最近一次心跳（heartbeat）时间
}
