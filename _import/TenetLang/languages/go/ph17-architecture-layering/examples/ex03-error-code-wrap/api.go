// 来源：ph17-architecture-layering examples/ex03-error-code-wrap/api.go
// 一句话说明：边界翻译层——唯一的"业务错误码 → HTTP 状态码"映射点。
// 纪律：状态码（404/400…）是传输层词汇，错误码（TODO_NOT_FOUND…）是业务层词汇，
// 两层词汇只在 handler 这里互相翻译；service 里永远不出现 http.StatusXxx。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"errors"
	"net/http"
)

type api struct {
	todos *todos
}

type renameRequest struct {
	Title string `json:"title"`
}

// errResponse 是统一的错误响应结构：{code, message}，与 roadmap §18 示例同构
// （字段结构从本阶段就统一，兼容性展开属 ph18）。
type errResponse struct {
	Code    Code   `json:"code"`
	Message string `json:"message"`
}

// renameHandler 是唯一的 Code→HTTP 映射处：errors.As 取回 *Error 再 switch Code。
func (a *api) renameHandler(w http.ResponseWriter, r *http.Request) {
	var req renameRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, New(CodeInvalid, "请求体不是合法 JSON"))
		return
	}
	if err := a.todos.rename(r.PathValue("id"), req.Title); err != nil {
		a.translate(w, err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// translate 把任意 error 翻译成 HTTP 响应：认识 *Error 就按 Code 映射，
// 不认识的一律兜底 500（内部错误不给调用方看细节）。
func (a *api) translate(w http.ResponseWriter, err error) {
	var de *Error
	if errors.As(err, &de) {
		switch de.Code {
		case CodeInvalid:
			writeError(w, http.StatusBadRequest, de)
		case CodeNotFound:
			writeError(w, http.StatusNotFound, de)
		default:
			writeError(w, http.StatusInternalServerError, New(Code("INTERNAL"), "internal error"))
		}
		return
	}
	writeError(w, http.StatusInternalServerError, New(Code("INTERNAL"), "internal error"))
}

func writeError(w http.ResponseWriter, status int, e *Error) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(errResponse{Code: e.Code, Message: e.Msg})
}
