// 来源：ph18-api-design-compat exercises/sol-02-error-schema（练习 2 参考实现）
// 一句话说明：统一错误结构的核心包 errs（roadmap §18 练习 2）。对外契约三件事：
// ① 结构：code/message 必填、requestId/details 可选（v2 追加，老客户端忽略未知字段）；
// ② 错误码注册表只增不删（Codes 全量 + 测试钉住历史集）；③ Go error 语义可用
// （*Error 实现 Unwrap，errors.Is/As 沿链追根因）。domain 词汇：任务管理系统 tasks。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .（打印错误码文档表）
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package errs

import (
	"encoding/json"
	"fmt"
)

// Code 稳定对外的错误码。code 是给机器读的：客户端 if 分支、监控告警规则、
// 错误码文档表都以它为键——所以语义一经发布就不许漂移（主文档 3.4）。
type Code string

// 错误码常量。新增 code 必须同步登记进 Codes()，并保证不在已发布语义上改名。
const (
	CodeValidation Code = "VALIDATION_ERROR" // 入参不合法（details 指明字段）
	CodeNotFound   Code = "TASK_NOT_FOUND"
	CodeConflict   Code = "TASK_CONFLICT" // 状态机冲突（已完成任务不可重开）
	CodeRateLimit  Code = "RATE_LIMITED"
	CodeInternal   Code = "INTERNAL"
)

// Detail 结构化定位"哪个字段、什么问题"（v2 追加的可选字段之一）。
type Detail struct {
	Field string `json:"field"`
	Issue string `json:"issue"`
}

// Error 对外错误结构。code/message 不带 omitempty = 永远出现；
// requestId/details 可选 = 老响应解析为 v2 结构时落在零值（向后兼容）。
type Error struct {
	Code      Code     `json:"code"`
	Message   string   `json:"message"`
	RequestID string   `json:"requestId,omitempty"`
	Details   []Detail `json:"details,omitempty"`

	Err error `json:"-"`
}

func (e *Error) Error() string { return fmt.Sprintf("%s: %s", e.Code, e.Message) }

// Unwrap 暴露内部根因，让 *Error 挂在标准错误链上。
func (e *Error) Unwrap() error { return e.Err }

// New 构造错误；cause 可为 nil。
func New(code Code, msg string, cause error) *Error {
	return &Error{Code: code, Message: msg, Err: cause}
}

// WithRequestID 注入请求追踪号（handler 出口在序列化前调用）。
func (e *Error) WithRequestID(id string) *Error {
	cp := *e
	cp.RequestID = id
	return &cp
}

// WithDetails 注入结构化字段错误。
func (e *Error) WithDetails(ds ...Detail) *Error {
	cp := *e
	cp.Details = append([]Detail(nil), ds...)
	return &cp
}

// EncodeJSON 序列化为响应体。
func (e *Error) EncodeJSON() ([]byte, error) { return json.Marshal(e) }
