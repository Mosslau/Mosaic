// 来源：ph17-architecture-layering examples/ex03-error-code-wrap/errs.go
// 一句话说明：领域错误码与包装错误。Code 面向调用方（前端/客户端，跨进程稳定），
// error 面向开发者（日志/排障）——两者通过 Error{Code, Msg, Err} 接起来：
// handler 只认 Code 映射 HTTP 状态，日志只看 Err 链找根因（主文档 3.6）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import "fmt"

// Code 是稳定对外的业务错误码。兼容纪律：字段只增不删、含义不漂移——
// 完整展开属 ph18 API 设计与兼容性阶段（roadmap 第 18 节，目录待建）。
type Code string

const (
	CodeInvalid  Code = "INVALID_ARGUMENT"
	CodeNotFound Code = "TODO_NOT_FOUND"
)

// Error 是带业务码的领域错误：Code 给调用方翻译用，Msg 是人类可读说明，
// Err 是底层原因（可为 nil），error 链可被 errors.Is/As 穿透。
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

// Unwrap 让包装链可见：errors.Is/As 会沿着它递归查找（主文档 4 底层原理）。
func (e *Error) Unwrap() error { return e.Err }

// New 构造无底层原因的领域错误。
func New(code Code, msg string) *Error {
	return &Error{Code: code, Msg: msg}
}

// Wrap 构造带底层原因的领域错误——"包装"而非"替换"，原因必须保留。
func Wrap(code Code, msg string, err error) *Error {
	return &Error{Code: code, Msg: msg, Err: err}
}
