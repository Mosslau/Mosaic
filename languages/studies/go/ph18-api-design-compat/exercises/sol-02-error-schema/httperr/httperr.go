// 来源：ph18-api-design-compat exercises/sol-02-error-schema/httperr/httperr.go
// 一句话说明：错误码 → HTTP 状态码的集中映射（roadmap §18 练习 2 的边界映射层）。
// 它是纯函数：不碰 w/r、不写网络，因此可脱离服务器单测。规则：
// ① 只认 *errs.Error（errors.As 取回）；② 没包成领域错误的未知类型一律兜底 500；
// ③ 集中映射表 = 换协议（gRPC、内部 RPC）时只改这一层（主文档 3.4）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package httperr

import (
	"errors"
	"net/http"

	"tenetlang/go/ph18-api-design-compat/exercises/sol-02-error-schema/errs"
)

// Map 把 error 翻译成 (HTTP 状态码, 对外错误结构)。调用方负责写响应，
// 映射本身保持纯函数——service 层只产生领域错误，翻译只在这一层发生一次。
func Map(err error) (int, errs.Error) {
	var e *errs.Error
	if !errors.As(err, &e) {
		// 未知错误类型：兜底 500，Message 用通用文案——真实原因在调用方日志里。
		return http.StatusInternalServerError, errs.Error{
			Code:    errs.CodeInternal,
			Message: "internal error",
			Err:     err,
		}
	}
	return codeHTTP(e.Code), *e
}

// codeHTTP 错误码 → HTTP 状态码映射表（多对一的集中登记处）。
func codeHTTP(c errs.Code) int {
	switch c {
	case errs.CodeValidation:
		return http.StatusBadRequest // 400
	case errs.CodeNotFound:
		return http.StatusNotFound // 404
	case errs.CodeConflict:
		return http.StatusConflict // 409
	case errs.CodeRateLimit:
		return http.StatusTooManyRequests // 429
	default:
		return http.StatusInternalServerError // 500 兜底（含 INTERNAL）
	}
}
