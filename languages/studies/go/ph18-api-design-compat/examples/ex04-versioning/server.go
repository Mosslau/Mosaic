// 来源：ph18-api-design-compat examples/ex04-versioning/server.go
// 一句话说明：v1/v2 共存的 handler。两个版本共享同一个 Store（业务层不感知版本），
// 差异只在：① 路由前缀；② 响应 DTO 裁剪；③ v1 额外带弃用通告头。
// Deprecation/Sunset 头是"通知客户端该搬家了"的标准信号（RFC 8594，主文档 3.3）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18104
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"net/http"
	"time"
)

// Server 版本共存服务。
type Server struct {
	store *Store
}

// NewServer 构造服务。
func NewServer() *Server { return &Server{store: NewStore()} }

// Register 注册 v1/v2 两组路由。它们指向不同的 handler，但底层是同一个 Store。
func (s *Server) Register(mux *http.ServeMux) {
	mux.HandleFunc("GET /v1/devices/{id}", s.handleGetV1)
	mux.HandleFunc("GET /v2/devices/{id}", s.handleGetV2)
}

// handleGetV1 v1 老版本：返回 v1 DTO + 弃用通告头。
func (s *Server) handleGetV1(w http.ResponseWriter, r *http.Request) {
	d, err := s.store.Get(r.PathValue("id"))
	if err != nil {
		writeError(w, http.StatusNotFound, "DEVICE_NOT_FOUND", "device not found")
		return
	}
	// Deprecation: true + Sunset 建议迁移期限——老版本还服务，但明确告知会下线。
	w.Header().Set("Deprecation", "true")
	w.Header().Set("Sunset", time.Now().AddDate(0, 6, 0).UTC().Format(http.TimeFormat))
	writeJSON(w, http.StatusOK, toV1(d))
}

// handleGetV2 v2 新版本：返回 v2 DTO（v1 字段一个不少，只是多了新字段）。
func (s *Server) handleGetV2(w http.ResponseWriter, r *http.Request) {
	d, err := s.store.Get(r.PathValue("id"))
	if err != nil {
		writeError(w, http.StatusNotFound, "DEVICE_NOT_FOUND", "device not found")
		return
	}
	writeJSON(w, http.StatusOK, toV2(d))
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, code, msg string) {
	writeJSON(w, status, map[string]string{"code": code, "message": msg})
}
