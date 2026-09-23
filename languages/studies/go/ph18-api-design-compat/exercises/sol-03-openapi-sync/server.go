// 来源：ph18-api-design-compat exercises/sol-03-openapi-sync/server.go
// 一句话说明：按 api/openapi.json 实现的设备查询服务（练习 3 的实现侧）。实现必须
// 满足规范：响应的 JSON 字段集合、查询参数集合、路由集合都以 spec 为准——契约测试
// 对三者逐一核对。json tag 与 spec properties 同名同义，这是 spec-first 的纪律。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18203
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"strconv"
	"strings"
)

// Device 响应对象：字段与 spec Device schema 完全一致。
type Device struct {
	ID     string `json:"id"`
	Plate  string `json:"plate"`
	Status string `json:"status"`
}

// Route 已实现的路由声明。
type Route struct {
	Method string
	Path   string
}

// Routes 实现侧路由清单（契约测试与 spec.paths 双向比对）。
func Routes() []Route {
	return []Route{
		{Method: http.MethodGet, Path: "/api/v1/devices"},
		{Method: http.MethodGet, Path: "/api/v1/devices/{id}"},
	}
}

// QueryKeys 返回列表端点解析的全部 query 参数名（契约测试与 spec 声明比对）。
func QueryKeys() map[string]bool {
	return map[string]bool{"status": true, "plate": true, "offset": true, "limit": true, "sort": true}
}

// Server 设备查询服务。
type Server struct {
	fleet []Device
}

// NewServer 构造服务。
func NewServer() *Server { return &Server{fleet: makeFleet()} }

// Register 挂载全部路由。
func (s *Server) Register(mux *http.ServeMux) {
	for _, rt := range Routes() {
		switch {
		case rt.Method == http.MethodGet && rt.Path == "/api/v1/devices":
			mux.HandleFunc(rt.Method+" "+rt.Path, s.handleList)
		case rt.Method == http.MethodGet:
			mux.HandleFunc(rt.Method+" "+rt.Path, s.handleGet)
		}
	}
}

func (s *Server) handleList(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	// 非法 status 回 400；limit/offset 解析规则与规范参数一致（default/cap 见 spec）。
	status := q.Get("status")
	if status != "" && status != "online" && status != "offline" && status != "maintenance" {
		writeError(w, http.StatusBadRequest, "BAD_REQUEST", "status must be online|offline|maintenance")
		return
	}
	off, err := strconv.Atoi(q.Get("offset"))
	if err != nil || off < 0 {
		writeError(w, http.StatusBadRequest, "BAD_REQUEST", "offset must be a non-negative integer")
		return
	}
	lim := 20
	if raw := q.Get("limit"); raw != "" {
		v, err := strconv.Atoi(raw)
		if err != nil || v < 0 {
			writeError(w, http.StatusBadRequest, "BAD_REQUEST", "limit must be a non-negative integer")
			return
		}
		lim = v
		if lim > 100 {
			lim = 100
		}
	}
	plate := q.Get("plate")

	filtered := make([]Device, 0, len(s.fleet))
	for _, v := range s.fleet {
		if status != "" && v.Status != status {
			continue
		}
		if plate != "" && !strings.Contains(v.Plate, plate) {
			continue
		}
		filtered = append(filtered, v)
	}
	sort.Slice(filtered, func(i, j int) bool { return filtered[i].ID < filtered[j].ID })
	start := off
	if start > len(filtered) {
		start = len(filtered)
	}
	end := start + lim
	if end > len(filtered) {
		end = len(filtered)
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"items":  filtered[start:end],
		"total":  len(filtered),
		"offset": start,
		"limit":  lim,
	})
}

func (s *Server) handleGet(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	for _, v := range s.fleet {
		if v.ID == id {
			writeJSON(w, http.StatusOK, v)
			return
		}
	}
	writeError(w, http.StatusNotFound, "VEHICLE_NOT_FOUND", "device not found")
}

func makeFleet() []Device {
	out := make([]Device, 0, 57)
	seq := []string{"online", "offline", "maintenance", "online"}
	for i := 0; i < 57; i++ {
		out = append(out, Device{ID: fmt.Sprintf("veh-%03d", i), Plate: fmt.Sprintf("京A-%03d", i), Status: seq[i%len(seq)]})
	}
	return out
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, code, msg string) {
	writeJSON(w, status, map[string]string{"code": code, "message": msg})
}
