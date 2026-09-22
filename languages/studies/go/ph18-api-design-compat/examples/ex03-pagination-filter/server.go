// 来源：ph18-api-design-compat examples/ex03-pagination-filter/server.go
// 一句话说明：列表接口的 handler。职责是"解析入参 → 调纯逻辑 Apply → 包 envelope"。
// 稳定性设计都写在注释里：limit 有默认值与硬上限、offset 拒绝负数、
// 非白名单 sort 回退默认而不报错（返回 400 会把"排序契约"变成一次承诺，见主文档 3.5）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18103
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"net/http"
	"strconv"
)

const (
	defaultLimit = 20 // 默认每页条数
	maxLimit     = 100
)

// Server 列表接口服务。
type Server struct {
	devices []Device // 固定数据集，无写接口（本示例聚焦读路径的稳定设计）
}

// NewServer 构造服务。
func NewServer() *Server { return &Server{devices: makeDataset(103)} }

// Register 挂载路由。分页参数刻意放在 query string 而不是路径段——
// 路径段是"资源定位"，query 是"视图调节"，混用会让 URL 语义混乱。
func (s *Server) Register(mux *http.ServeMux) {
	mux.HandleFunc("GET /v1/devices", s.handleList)
}

// parseQuery 解析列表查询参数。返回 (Query, ok)：ok=false 表示入参非法已写响应。
func (s *Server) parseQuery(w http.ResponseWriter, r *http.Request) (Query, bool) {
	q := r.URL.Query()
	var out Query
	out.Status = q.Get("status")
	if out.Status != "" && out.Status != "online" && out.Status != "offline" && out.Status != "maintenance" {
		writeError(w, http.StatusBadRequest, "BAD_REQUEST", "status must be one of online|offline|maintenance")
		return out, false
	}
	out.Q = q.Get("q")
	out.Sort = q.Get("sort")

	off := 0
	if raw := q.Get("offset"); raw != "" { // 缺省 offset=0，不必要求客户端显式传
		v, err := strconv.Atoi(raw)
		if err != nil || v < 0 {
			writeError(w, http.StatusBadRequest, "BAD_REQUEST", "offset must be a non-negative integer")
			return out, false
		}
		off = v
	}
	out.Offset = off

	lim := 0
	if raw := q.Get("limit"); raw != "" { // 缺省走默认 limit（defaultLimit）
		v, err := strconv.Atoi(raw)
		if err != nil || v < 0 {
			writeError(w, http.StatusBadRequest, "BAD_REQUEST", "limit must be a non-negative integer")
			return out, false
		}
		lim = v
	}
	switch {
	case lim == 0:
		out.Limit = defaultLimit // 缺省给默认值
	case lim > maxLimit:
		out.Limit = maxLimit // 超上限截断：防恶意大 offset+limit 拖垮服务
	default:
		out.Limit = lim
	}
	return out, true
}

func (s *Server) handleList(w http.ResponseWriter, r *http.Request) {
	q, ok := s.parseQuery(w, r)
	if !ok {
		return
	}
	writeJSON(w, http.StatusOK, Apply(s.devices, q))
}
