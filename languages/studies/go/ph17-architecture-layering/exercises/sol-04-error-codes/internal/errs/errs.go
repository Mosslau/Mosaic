// 来源：ph17-architecture-layering exercises/sol-04-error-codes/internal/errs
// 一句话说明：错误码包（练习 4 参考实现）。Code 是稳定对外的业务码，
// Error 把 Code/Msg/根因 Err 捆在一起；errors.Is/As 沿 Unwrap 穿透。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package errs

import "fmt"

// Code 稳定对外错误码。兼容纪律：只增不删（ph18 API 设计与兼容性阶段展开）。
type Code string

const (
	CodeNotFound   Code = "ORDER_NOT_FOUND"
	CodeConflict   Code = "ORDER_STATE_CONFLICT"
	CodeBadRequest Code = "BAD_REQUEST"
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

func (e *Error) Unwrap() error { return e.Err }

func New(code Code, msg string) *Error {
	return &Error{Code: code, Msg: msg}
}

func Wrap(code Code, msg string, err error) *Error {
	return &Error{Code: code, Msg: msg, Err: err}
}
