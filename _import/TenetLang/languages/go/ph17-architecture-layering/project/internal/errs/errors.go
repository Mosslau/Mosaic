// 来源：ph17-architecture-layering project/internal/errs
// 一句话说明：业务错误码包。Code 是稳定对外的业务码（响应 JSON 的 code 字段），
// Error{Code, Msg, Err} 把"给调用方的码 + 给开发者的根因链"捆在一起。
// 兼容纪律：对外发布的 Code 只增不删（完整展开属 ph18 API 设计与兼容性阶段）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package errs

import "fmt"

// Code 稳定对外错误码（本项目的节点管理域词汇）。
type Code string

const (
	CodeBadRequest Code = "BAD_REQUEST"
	CodeNotFound   Code = "NODE_NOT_FOUND"
	CodeExists     Code = "NODE_EXISTS"
	CodeOffline    Code = "NODE_OFFLINE"
	CodeConflict   Code = "CONFLICT"
	CodeInternal   Code = "INTERNAL"
)

// Error 带业务码的领域错误。
type Error struct {
	Code Code
	Msg  string
	Err  error
}

func (e *Error) Error() string {
	if e.Err != nil {
		return fmt.Sprintf("%s: %s (cause: %v)", e.Code, e.Msg, e.Err)
	}
	return fmt.Sprintf("%s: %s", e.Code, e.Msg)
}

// Unwrap 让包装链可被 errors.Is/As 穿透（根因必须可追溯）。
func (e *Error) Unwrap() error { return e.Err }

// New 无根因错误（纯业务规则拒绝）。
func New(code Code, msg string) *Error {
	return &Error{Code: code, Msg: msg}
}

// Newf 格式化消息的无根因错误。
func Newf(code Code, format string, args ...any) *Error {
	return &Error{Code: code, Msg: fmt.Sprintf(format, args...)}
}

// Wrap 带根因的包装错误（存储层故障等）。
func Wrap(code Code, msg string, err error) *Error {
	return &Error{Code: code, Msg: msg, Err: err}
}
