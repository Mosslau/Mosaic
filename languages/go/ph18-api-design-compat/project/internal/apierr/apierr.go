// 来源：ph18-api-design-compat project/internal/apierr/apierr.go
// 一句话说明：错误码注册表（集中、只增不删）+ 领域错误类型。对外 code 语义：
// 与 api/openapi.json 的 Error schema 配套——code 是给机器读的，message 是给
// 人读的。handler 只在唯一出口把 *Error 翻译成 HTTP（主文档 3.4/3.6）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package apierr

import "fmt"

// Code 稳定对外错误码。
type Code string

// 对外错误码。新增必须登记进 Codes()；历史 code 永不可删（apierr_test 钉住）。
const (
	CodeBadRequest Code = "BAD_REQUEST"
	CodeNotFound   Code = "DEVICE_NOT_FOUND"
	CodeInternal   Code = "INTERNAL"
)

// Error 对外错误结构：code/message 必填永在；Err 只进日志（json:"-"）。
type Error struct {
	Code    Code   `json:"code"`
	Message string `json:"message"`
	Err     error  `json:"-"`
}

func (e *Error) Error() string { return fmt.Sprintf("%s: %s", e.Code, e.Message) }

// Unwrap 暴露根因。
func (e *Error) Unwrap() error { return e.Err }

// New 构造领域错误。
func New(c Code, msg string, cause error) *Error {
	return &Error{Code: c, Message: msg, Err: cause}
}

// 注册表：登记每个对外 code（含首次发布版本与语义）。删除 = 破坏性变更。
var registry = []struct {
	Code    Code
	Since   string
	Meaning string
}{
	{CodeBadRequest, "v1.0", "入参不合法（非法参数值/坏 JSON）"},
	{CodeNotFound, "v1.0", "设备不存在（查询/注销目标缺失）"},
	{CodeInternal, "v1.0", "服务内部错误（兜底；细节只进日志）"},
}

// Codes 全量对外错误码（顺序即文档表顺序）。
func Codes() []Code {
	out := make([]Code, 0, len(registry))
	for _, r := range registry {
		out = append(out, r.Code)
	}
	return out
}
