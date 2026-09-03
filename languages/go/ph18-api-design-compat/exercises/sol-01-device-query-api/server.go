// 来源：ph18-api-design-compat exercises/sol-01-device-query-api（练习 1 参考实现）
// 一句话说明：HTTP 接入层：解析入参（边界校验）→ 调 Apply → 写 envelope。
// 非法入参回 400 + 统一错误体 {code,message}；合法但未知的 sort 字段回退默认，
// 因为"排序能力"也是一种会被客户端依赖的契约——给得越少承诺越稳（主文档 3.5）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18201
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"net/http"
	"strconv"
)

const (
	defaultLimit = 20
	maxLimit     = 100
)

// Server 车辆查询服务。
type Server struct {
	fleet []Vehicle
}

// NewServer 构造服务。
func NewServer() *Server { return &Server{fleet: makeFleet()} }

// Register 挂载路由。
func (s *Server) Register(mux *http.ServeMux) {
	mux.HandleFunc("GET /api/v1/vehicles", s.handleList)
	mux.HandleFunc("GET /api/v1/vehicles/{id}", s.handleGet)
}

func (s *Server) handleList(w http.ResponseWriter, r *http.Request) {
	q := parseQuery(w, r)
	if q == nil {
		return // parseQuery 已写响应
	}
	writeJSON(w, http.StatusOK, Apply(s.fleet, *q))
}

func (s *Server) handleGet(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	for _, v := range s.fleet {
		if v.ID == id {
			writeJSON(w, http.StatusOK, v)
			return
		}
	}
	writeError(w, http.StatusNotFound, "VEHICLE_NOT_FOUND", "vehicle not found")
}

// parseQuery 解析并校验查询参数；非法时写 400 并返回 nil。
func parseQuery(w http.ResponseWriter, r *http.Request) *Query {
	q := r.URL.Query()
	out := &Query{Status: q.Get("status"), Plate: q.Get("plate"), Sort: q.Get("sort")}
	if out.Status != "" && out.Status != "online" && out.Status != "offline" && out.Status != "maintenance" {
		writeError(w, http.StatusBadRequest, "BAD_REQUEST", "status must be online|offline|maintenance")
		return nil
	}
	off := 0
	if raw := q.Get("offset"); raw != "" {
		v, err := strconv.Atoi(raw)
		if err != nil || v < 0 {
			writeError(w, http.StatusBadRequest, "BAD_REQUEST", "offset must be a non-negative integer")
			return nil
		}
		off = v
	}
	out.Offset = off
	lim := 0
	if raw := q.Get("limit"); raw != "" {
		v, err := strconv.Atoi(raw)
		if err != nil || v < 0 {
			writeError(w, http.StatusBadRequest, "BAD_REQUEST", "limit must be a non-negative integer")
			return nil
		}
		lim = v
	}
	switch {
	case lim == 0:
		out.Limit = defaultLimit
	case lim > maxLimit:
		out.Limit = maxLimit
	default:
		out.Limit = lim
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
