// 来源：ph18-api-design-compat examples/ex02-error-struct-evolution/errs.go
// 一句话说明：错误结构的稳定与演进实验（主文档 3.4）。对外错误结构从 v1 的
// {code,message} 演进到 v2 的 {code,message,requestId,details}：
// ① code 只增不删、语义不漂移（对外的稳定标识）；② message 是给人看的说明，可改不可删；
// ③ 新字段只能"追加"（向前兼容：老客户端按未知字段忽略）；④ 核心字段 code/message 永在。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .（打印 v1/v2 序列化对比）
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"fmt"
)

// Code 是"稳定对外"的错误码类型。Code 本身是文档的一部分：任何一个对外出现的
// Code 都应在注册表（publishedCodes）里登记——"错误码只增不删"由此可被测试钉住。
type Code string

// 业务错误码常量。新增 Code 时必须同步加进 publishedCodes 注册表。
const (
	CodeBadRequest  Code = "BAD_REQUEST"
	CodeNotFound    Code = "DEVICE_NOT_FOUND"
	CodeConflict    Code = "CONFLICT"
	CodeUnavailable Code = "UNAVAILABLE"
	CodeInternal    Code = "INTERNAL"
)

// publishedCodes 是"已对外发布过"的错误码注册表（含首次发布语义）。
// 演进纪律：只允许在末尾追加，绝不删除、绝不复用——删除会让依赖该 code 的
// 老客户端把错误当成未知错误处理（主文档 3.4 的"删码是破坏性变更"）。
func publishedCodes() []Code {
	return []Code{
		CodeBadRequest,  // v1.0：入参不合法
		CodeNotFound,    // v1.0：资源不存在
		CodeConflict,    // v1.1：状态冲突（如固件版本回退）
		CodeUnavailable, // v2.0：依赖暂不可用（可重试）
		CodeInternal,    // v1.0：兜底内部错误
	}
}

// Detail 是 v2 新增的字段：结构化定位"哪个字段、什么问题"。
type Detail struct {
	Field string `json:"field"`
	Issue string `json:"issue"`
}

// Error 是对外的错误结构。序列化字段即对外契约（json tag 即字段名）。
// code/message 不带 omitempty：这两个字段任何时候都必须出现（核心字段永在）。
// requestId/details 是 v2 追加的可选字段：老客户端忽略未知字段即可无痛升级。
type Error struct {
	Code      Code     `json:"code"`
	Message   string   `json:"message"`
	RequestID string   `json:"requestId,omitempty"`
	Details   []Detail `json:"details,omitempty"`

	Err error `json:"-"` // 内部根因，只进日志不出响应体（不序列化）
}

func (e *Error) Error() string { return fmt.Sprintf("%s: %s", e.Code, e.Message) }

// Unwrap 让 *Error 挂在标准错误链上，errors.Is/As 可以沿链追到根因。
func (e *Error) Unwrap() error { return e.Err }

// New 构造一个对外错误；cause 为内部根因（可为 nil）。
func New(code Code, msg string, cause error) *Error {
	return &Error{Code: code, Message: msg, Err: cause}
}

// WithRequestID 返回带 requestId 的副本（HTTP 边界注入，便于调用方报障时定位日志）。
func (e *Error) WithRequestID(id string) *Error {
	cp := *e
	cp.RequestID = id
	return &cp
}

// WithDetails 返回追加 details 的副本（用于"哪个字段不合法"这类结构化提示）。
func (e *Error) WithDetails(details ...Detail) *Error {
	cp := *e
	cp.Details = append([]Detail(nil), details...)
	return &cp
}

// EncodeJSON 序列化为 JSON 响应体（用于 handler 出口，测试可直接断言结构）。
func (e *Error) EncodeJSON() ([]byte, error) { return json.Marshal(e) }
