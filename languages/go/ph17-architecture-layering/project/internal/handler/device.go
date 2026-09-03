// 来源：ph17-architecture-layering project/internal/handler
// 一句话说明：HTTP 接入层。所有端点 = 解码请求 → 调 service → 写响应（JSON/状态码）。
// 业务规则不在此出现；错误统一交给 fail()：errors.As 取回 *errs.Error 后按 Code
// 映射 HTTP 状态——这是全项目唯一做"业务码 ↔ 传输状态码"翻译的地方。
// 响应直接序列化 domain.Device（json tag 教学简化，见主文档 3.2）。
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
	"log/slog"
	"net/http"

	"tenetlang/go/ph17-architecture-layering/project/internal/errs"
	"tenetlang/go/ph17-architecture-layering/project/internal/service"
)

// Handler 接入层：只依赖 service 接口的具象门面 + 日志器。
type Handler struct {
	svc    *service.Service
	logger *slog.Logger
}

func New(svc *service.Service, logger *slog.Logger) *Handler {
	return &Handler{svc: svc, logger: logger}
}

// Register 挂载全部路由（Go 1.22+ 方法路由，见 ph09 Web 后端开发阶段）。
func (h *Handler) Register(mux *http.ServeMux) {
	mux.HandleFunc("GET /healthz", h.health)
	mux.HandleFunc("POST /api/devices", h.create)
	mux.HandleFunc("GET /api/devices", h.list)
	mux.HandleFunc("GET /api/devices/{id}", h.get)
	mux.HandleFunc("DELETE /api/devices/{id}", h.delete)
	mux.HandleFunc("POST /api/devices/{id}/heartbeat", h.heartbeat)
	mux.HandleFunc("POST /api/devices/{id}/firmware", h.upgrade)
	mux.HandleFunc("POST /api/devices/{id}/commands", h.command)
}

// ---- 请求/响应结构（接入层词汇，见主文档 3.2）----

type createRequest struct {
	ID       string `json:"id"`
	Name     string `json:"name"`
	Firmware string `json:"firmware"`
}

type firmwareRequest struct {
	Version string `json:"version"`
}

type commandRequest struct {
	Command string `json:"command"`
}

type ackResponse struct {
	Status string `json:"status"`
}

type errBody struct {
	Code    errs.Code `json:"code"`
	Message string    `json:"message"`
}

// ---- 端点 ----

func (h *Handler) health(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, ackResponse{Status: "ok"})
}

func (h *Handler) create(w http.ResponseWriter, r *http.Request) {
	var req createRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.fail(w, r, errs.New(errs.CodeBadRequest, "请求体不是合法 JSON"))
		return
	}
	d, err := h.svc.Register(req.ID, req.Name, req.Firmware)
	if err != nil {
		h.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusCreated, d)
}

func (h *Handler) list(w http.ResponseWriter, r *http.Request) {
	devices, err := h.svc.List()
	if err != nil {
		h.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, devices)
}

func (h *Handler) get(w http.ResponseWriter, r *http.Request) {
	d, err := h.svc.Get(r.PathValue("id"))
	if err != nil {
		h.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, d)
}

func (h *Handler) delete(w http.ResponseWriter, r *http.Request) {
	if err := h.svc.Delete(r.PathValue("id")); err != nil {
		h.fail(w, r, err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (h *Handler) heartbeat(w http.ResponseWriter, r *http.Request) {
	d, err := h.svc.Heartbeat(r.PathValue("id"))
	if err != nil {
		h.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, d)
}

func (h *Handler) upgrade(w http.ResponseWriter, r *http.Request) {
	var req firmwareRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.fail(w, r, errs.New(errs.CodeBadRequest, "请求体不是合法 JSON"))
		return
	}
	d, err := h.svc.UpgradeFirmware(r.PathValue("id"), req.Version)
	if err != nil {
		h.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, d)
}

func (h *Handler) command(w http.ResponseWriter, r *http.Request) {
	var req commandRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.fail(w, r, errs.New(errs.CodeBadRequest, "请求体不是合法 JSON"))
		return
	}
	if err := h.svc.SendCommand(r.PathValue("id"), req.Command); err != nil {
		h.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusAccepted, ackResponse{Status: "accepted"})
}

// ---- 翻译与写响应（唯一映射点 + 统一错误结构）----

// fail 是"错误 → HTTP 响应"的唯一出口：认识 *errs.Error 按 Code 查表；
// 未知错误类型兜底 500 并记日志（真实原因只进日志，不进响应体）。
func (h *Handler) fail(w http.ResponseWriter, r *http.Request, err error) {
	var de *errs.Error
	if errors.As(err, &de) {
		switch de.Code {
		case errs.CodeBadRequest:
			h.writeErr(w, http.StatusBadRequest, de)
		case errs.CodeNotFound:
			h.writeErr(w, http.StatusNotFound, de)
		case errs.CodeExists, errs.CodeOffline, errs.CodeConflict:
			h.writeErr(w, http.StatusConflict, de)
		default:
			h.logger.Error("internal error", "method", r.Method, "path", r.URL.Path, "err", err)
			h.writeErr(w, http.StatusInternalServerError, de)
		}
		return
	}
	h.logger.Error("unexpected error", "method", r.Method, "path", r.URL.Path, "err", err)
	h.writeErr(w, http.StatusInternalServerError, errs.New(errs.CodeInternal, "internal error"))
}

func (h *Handler) writeErr(w http.ResponseWriter, status int, e *errs.Error) {
	writeJSON(w, status, errBody{Code: e.Code, Message: e.Msg})
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	// 响应已开始后编码错误无法再改状态码，显式忽略（L3：best-effort）
	_ = json.NewEncoder(w).Encode(v)
}
