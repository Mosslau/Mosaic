// 来源：ph17-architecture-layering exercises/sol-01-layered-todo/internal/handler
// 一句话说明：练习 1 参考实现的接入层。五个端点只做"解码 → 调 service → 编码"，
// 业务词汇（优先级校验失败）一律通过错误语义判断，不在此重写规则。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package handler

import (
	"encoding/json"
	"errors"
	"net/http"

	"tenetlang/go/ph17-architecture-layering/exercises/sol-01-layered-todo/internal/service"
	"tenetlang/go/ph17-architecture-layering/exercises/sol-01-layered-todo/internal/store"
	"tenetlang/go/ph17-architecture-layering/exercises/sol-01-layered-todo/internal/todo"
)

type Handler struct {
	svc *service.Service
}

func New(svc *service.Service) *Handler {
	return &Handler{svc: svc}
}

func (h *Handler) Register(mux *http.ServeMux) {
	mux.HandleFunc("GET /todos", h.list)
	mux.HandleFunc("POST /todos", h.create)
	mux.HandleFunc("GET /todos/{id}", h.get)
	mux.HandleFunc("POST /todos/{id}/toggle", h.toggle)
	mux.HandleFunc("DELETE /todos/{id}", h.delete)
}

type createRequest struct {
	Title    string `json:"title"`
	Priority string `json:"priority"`
}

func (h *Handler) list(w http.ResponseWriter, r *http.Request) {
	items, err := h.svc.List()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal error")
		return
	}
	writeJSON(w, http.StatusOK, items)
}

func (h *Handler) create(w http.ResponseWriter, r *http.Request) {
	var req createRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	t, err := h.svc.Add(req.Title, priorityOf(req.Priority))
	if err != nil {
		if errors.Is(err, service.ErrBadRequest) {
			writeError(w, http.StatusBadRequest, err.Error())
			return
		}
		writeError(w, http.StatusInternalServerError, "internal error")
		return
	}
	writeJSON(w, http.StatusCreated, t)
}

// priorityOf 把请求字符串转成领域词：类型转换是接入层职责，合法性校验在 service
// （service.Add 收到非法值会回 ErrBadRequest——错误最终由 service 说了算）。
func priorityOf(s string) todo.Priority {
	return todo.Priority(s)
}

func (h *Handler) get(w http.ResponseWriter, r *http.Request) {
	t, err := h.svc.Get(r.PathValue("id"))
	if err != nil {
		if errors.Is(err, store.ErrNotFound) {
			writeError(w, http.StatusNotFound, "not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "internal error")
		return
	}
	writeJSON(w, http.StatusOK, t)
}

func (h *Handler) toggle(w http.ResponseWriter, r *http.Request) {
	t, err := h.svc.Toggle(r.PathValue("id"))
	if err != nil {
		if errors.Is(err, store.ErrNotFound) {
			writeError(w, http.StatusNotFound, "not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "internal error")
		return
	}
	writeJSON(w, http.StatusOK, t)
}

func (h *Handler) delete(w http.ResponseWriter, r *http.Request) {
	if err := h.svc.Delete(r.PathValue("id")); err != nil {
		if errors.Is(err, store.ErrNotFound) {
			writeError(w, http.StatusNotFound, "not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "internal error")
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}
