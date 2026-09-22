// 来源：ph18-api-design-compat project/internal/devices/handler.go
// 一句话说明：版本化 HTTP 接入层（spec-first 的实现侧）。三条契约纪律的落点：
// ① 路由清单 = Routes()，Register 只允许挂载清单内的路由（与 spec.paths 对账的锚点）；
// ② v1/v2 共享同一 Store，差异只在 DTO 裁剪与参数能力（v2 多 sort）——
// "加版本"不复制业务，只加一个裁剪分支；
// ③ 错误只在 writeError 出口集中映射成 {code,message}（apierr 注册表）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package devices

import (
	"encoding/json"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"time"

	"tenetlang/go/ph18-api-design-compat/project/internal/apierr"
)

const (
	defaultLimit = 20
	maxLimit     = 100
)

// Route 一条对外路由（与 spec.paths 双向对账的最小单元）。
type Route struct {
	Method string
	Path   string
}

// Routes 服务实现的路由清单。契约测试要求：spec 声明 ⇔ 本清单，双向一一对应。
func Routes() []Route {
	return []Route{
		{Method: http.MethodGet, Path: "/v1/devices"},
		{Method: http.MethodPost, Path: "/v1/devices"},
		{Method: http.MethodGet, Path: "/v1/devices/{id}"},
		{Method: http.MethodDelete, Path: "/v1/devices/{id}"},
		{Method: http.MethodGet, Path: "/v2/devices"},
		{Method: http.MethodGet, Path: "/v2/devices/{id}"},
	}
}

// QueryKeys 返回指定版本列表端点实际解析的 query 参数名集合（供契约测试对账）。
func QueryKeys(version string) map[string]bool {
	base := map[string]bool{"status": true, "offset": true, "limit": true}
	if version == "v2" {
		base["sort"] = true // v2 新增的查询能力——能力也要写进 spec 才能用
	}
	return base
}

// Handler 版本化设备接口。
type Handler struct {
	store *Store
}

// New 构造 handler。
func New(st *Store) *Handler { return &Handler{store: st} }

// Register 挂载 Routes() 声明的全部路由。
func (h *Handler) Register(mux *http.ServeMux) {
	mux.HandleFunc("GET /v1/devices", h.handleList("v1"))
	mux.HandleFunc("GET /v2/devices", h.handleList("v2"))
	mux.HandleFunc("POST /v1/devices", h.handleCreate)
	mux.HandleFunc("GET /v1/devices/{id}", h.handleGet("v1"))
	mux.HandleFunc("GET /v2/devices/{id}", h.handleGet("v2"))
	mux.HandleFunc("DELETE /v1/devices/{id}", h.handleDelete)
}

// handleList 列表接口：按版本决定视图与排序能力。v1 固定按 id 排序，
// v2 接受 sort=name（白名单）；过滤/分页规则两版共用同一段代码。
func (h *Handler) handleList(version string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		q := r.URL.Query()

		status := q.Get("status")
		if status != "" && status != "online" && status != "offline" && status != "maintenance" {
			writeError(w, http.StatusBadRequest, apierr.CodeBadRequest, "status must be online|offline|maintenance")
			return
		}
		off := 0
		if raw := q.Get("offset"); raw != "" { // 缺省 offset=0，不必显式传
			v, err := strconv.Atoi(raw)
			if err != nil || v < 0 {
				writeError(w, http.StatusBadRequest, apierr.CodeBadRequest, "offset must be a non-negative integer")
				return
			}
			off = v
		}
		lim := defaultLimit
		if raw := q.Get("limit"); raw != "" {
			v, err := strconv.Atoi(raw)
			if err != nil || v < 0 {
				writeError(w, http.StatusBadRequest, apierr.CodeBadRequest, "limit must be a non-negative integer")
				return
			}
			lim = min(v, maxLimit)
		}

		all := h.store.All()
		filtered := make([]Device, 0, len(all))
		for _, d := range all {
			if status != "" && !statusMatches(d, status) {
				continue
			}
			filtered = append(filtered, d)
		}

		// v2 的 sort 能力；v1 时代不承诺排序参数，固定 id 序（契约不扩大）。
		if version == "v2" && q.Get("sort") == "name" {
			sort.Slice(filtered, func(i, j int) bool {
				if filtered[i].Name != filtered[j].Name {
					return filtered[i].Name < filtered[j].Name
				}
				return filtered[i].ID < filtered[j].ID // 同值决胜：翻页稳定
			})
		}

		start := min(off, len(filtered))
		end := min(start+lim, len(filtered))
		writeList(w, http.StatusOK, version, filtered[start:end])
	}
}

// statusMatches 过滤语义映射。本 demo 数据集只有 online/offline 两台设备，
// maintenance 是契约允许的值但当前数据里没有——过滤结果为空集是合法语义。
func statusMatches(d Device, status string) bool {
	switch status {
	case "online":
		return d.Online
	case "offline":
		return !d.Online
	default: // maintenance
		return false
	}
}

// handleGet 单设备查询。
func (h *Handler) handleGet(version string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		d, ok := h.store.Get(r.PathValue("id"))
		if !ok {
			writeError(w, http.StatusNotFound, apierr.CodeNotFound, "device not found")
			return
		}
		if version == "v1" {
			// v1 已弃用：通告头是"该搬家了"的显式信号（RFC 8594）。
			w.Header().Set("Deprecation", "true")
			w.Header().Set("Sunset", time.Now().AddDate(0, 6, 0).UTC().Format(http.TimeFormat))
		}
		writeSingle(w, http.StatusOK, version, d)
	}
}

// handleCreate 注册设备（POST 非幂等，服务端分配 id；v1/v2 共用同一语义，
// 创建入口只有 /v1/devices——新增端点才算新能力，见主文档 3.3）。
func (h *Handler) handleCreate(w http.ResponseWriter, r *http.Request) {
	var in struct {
		Name string `json:"name"`
	}
	if err := json.NewDecoder(r.Body).Decode(&in); err != nil {
		writeError(w, http.StatusBadRequest, apierr.CodeBadRequest, "invalid json body")
		return
	}
	if strings.TrimSpace(in.Name) == "" {
		writeError(w, http.StatusBadRequest, apierr.CodeBadRequest, "name is required")
		return
	}
	d := h.store.Add(in.Name)
	w.Header().Set("Location", "/v1/devices/"+d.ID)
	writeSingle(w, http.StatusCreated, "v1", d)
}

// handleDelete 注销设备（幂等：不存在也 204，与 DELETE 语义一致）。
func (h *Handler) handleDelete(w http.ResponseWriter, r *http.Request) {
	h.store.Delete(r.PathValue("id"))
	w.WriteHeader(http.StatusNoContent)
}

// writeList 按版本序列化设备列表（数组形态）。
func writeList(w http.ResponseWriter, status int, version string, devices []Device) {
	if version == "v2" {
		out := make([]DeviceV2, 0, len(devices))
		for _, d := range devices {
			out = append(out, toV2(d))
		}
		writeJSON(w, status, out)
		return
	}
	out := make([]DeviceV1, 0, len(devices))
	for _, d := range devices {
		out = append(out, toV1(d))
	}
	writeJSON(w, status, out)
}

// writeSingle 按版本序列化单对象（对象形态）。
func writeSingle(w http.ResponseWriter, status int, version string, d Device) {
	if version == "v2" {
		writeJSON(w, status, toV2(d))
		return
	}
	writeJSON(w, status, toV1(d))
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

// writeError 唯一错误出口：code 语义来自 apierr 注册表，Message 人类可读，
// 根因（若有）只进调用方日志，不进响应体。
func writeError(w http.ResponseWriter, status int, code apierr.Code, msg string) {
	writeJSON(w, status, map[string]string{"code": string(code), "message": msg})
}
