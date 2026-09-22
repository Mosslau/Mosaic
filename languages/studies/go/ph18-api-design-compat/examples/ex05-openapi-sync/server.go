// 来源：ph18-api-design-compat examples/ex05-openapi-sync/server.go
// 一句话说明：按规范实现的设备服务（spec-first 的实现侧）。要点：响应结构体的
// json tag 就是"实现对外承诺的字段集合"，契约测试会让它与 openapi.json 的
// schema properties 对不上时立刻失败——文档与实现漂移被拦截在 CI（主文档 3.7）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18105
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"sync"
)

// Device 响应模型。json tag 名与 api/openapi.json 中 Device schema 的 properties
// 一一对应——这就是"文档与实现同步"的字段级承诺（契约测试逐一核对）。
type Device struct {
	ID     string `json:"id"`
	Name   string `json:"name"`
	Online bool   `json:"online"`
}

// input 创建入参：仅 name（对应 DeviceInput schema）。
type input struct {
	Name string `json:"name"`
}

// Route 一条已实现的路由（method + path）。Routes 表是实现侧的"路由清单"，
// 契约测试用它和 spec.paths 做双向比对。
type Route struct {
	Method string
	Path   string
}

// Routes 返回服务实现的全部对外路由。路径占位符写法与 OpenAPI 一致（{id}）。
func Routes() []Route {
	return []Route{
		{Method: http.MethodGet, Path: "/v1/devices"},
		{Method: http.MethodPost, Path: "/v1/devices"},
		{Method: http.MethodGet, Path: "/v1/devices/{id}"},
		{Method: http.MethodDelete, Path: "/v1/devices/{id}"},
	}
}

// Server 设备服务。Register 内部校验"每个注册的路由都声明在 Routes 中"，
// 防止某 handler 悄悄挂了一个没进清单的接口（实现漂移的第二道防线）。
type Server struct {
	mu   sync.RWMutex
	next int
	byID map[string]Device
}

// NewServer 构造服务。
func NewServer() *Server {
	return &Server{
		next: 2,
		byID: map[string]Device{
			"car-001": {ID: "car-001", Name: "1号车", Online: true},
			"car-002": {ID: "car-002", Name: "2号车", Online: false},
		},
	}
}

// Register 注册全部路由（挂载点就是 Routes() 声明的集合）。
func (s *Server) Register(mux *http.ServeMux) {
	for _, rt := range Routes() {
		pattern := rt.Method + " " + rt.Path
		switch rt.Method {
		case http.MethodGet:
			if rt.Path == "/v1/devices" {
				mux.HandleFunc(pattern, s.handleList)
			} else {
				mux.HandleFunc(pattern, s.handleGet)
			}
		case http.MethodPost:
			mux.HandleFunc(pattern, s.handleCreate)
		case http.MethodDelete:
			mux.HandleFunc(pattern, s.handleDelete)
		}
	}
}

func (s *Server) handleList(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	out := make([]Device, 0, len(s.byID))
	for _, d := range s.byID {
		out = append(out, d)
	}
	s.mu.RUnlock()
	writeJSON(w, http.StatusOK, out)
}

func (s *Server) handleGet(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	d, ok := s.byID[r.PathValue("id")]
	s.mu.RUnlock()
	if !ok {
		writeError(w, http.StatusNotFound, "DEVICE_NOT_FOUND", "device not found")
		return
	}
	writeJSON(w, http.StatusOK, d)
}

func (s *Server) handleCreate(w http.ResponseWriter, r *http.Request) {
	var in input
	if err := json.NewDecoder(r.Body).Decode(&in); err != nil {
		writeError(w, http.StatusBadRequest, "BAD_REQUEST", "invalid json body")
		return
	}
	if strings.TrimSpace(in.Name) == "" {
		writeError(w, http.StatusBadRequest, "BAD_REQUEST", "name is required")
		return
	}
	s.mu.Lock()
	s.next++
	id := fmt.Sprintf("car-%03d", s.next)
	d := Device{ID: id, Name: in.Name}
	s.byID[id] = d
	s.mu.Unlock()
	w.Header().Set("Location", "/v1/devices/"+id)
	writeJSON(w, http.StatusCreated, d)
}

func (s *Server) handleDelete(w http.ResponseWriter, r *http.Request) {
	s.mu.Lock()
	delete(s.byID, r.PathValue("id")) // 幂等：不存在也 204
	s.mu.Unlock()
	w.WriteHeader(http.StatusNoContent)
}
