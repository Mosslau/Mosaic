// 来源：ph17-architecture-layering exercises/sol-04-error-codes/internal/httperr
// 一句话说明：边界翻译层（练习 4 参考实现）。Map 是"领域错误 → HTTP 状态码与响应体"
// 的唯一纯函数：handler 调它即可，映射逻辑可脱离服务器单测。
// 纪律：内部错误（未知类型/未列出的 Code）一律兜底 500，消息不透出细节。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package httperr

import (
	"errors"
	"net/http"

	"tenetlang/go/ph17-architecture-layering/exercises/sol-04-error-codes/internal/errs"
)

// Body 统一错误响应结构（与 roadmap §18 示例同构）。
type Body struct {
	Code    errs.Code `json:"code"`
	Message string    `json:"message"`
}

// Map 唯一映射点：*errs.Error 按 Code 查表；其它错误类型兜底 500。
func Map(err error) (int, Body) {
	var de *errs.Error
	if errors.As(err, &de) {
		switch de.Code {
		case errs.CodeNotFound:
			return http.StatusNotFound, Body{Code: de.Code, Message: de.Msg}
		case errs.CodeConflict:
			return http.StatusConflict, Body{Code: de.Code, Message: de.Msg}
		case errs.CodeBadRequest:
			return http.StatusBadRequest, Body{Code: de.Code, Message: de.Msg}
		default:
			return http.StatusInternalServerError, Body{Code: errs.CodeInternal, Message: "internal error"}
		}
	}
	// 未知错误类型：真实原因应已记日志（handler 侧），响应只给兜底文案
	return http.StatusInternalServerError, Body{Code: errs.CodeInternal, Message: "internal error"}
}
