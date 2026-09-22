// 来源：ph18-api-design-compat examples/ex01-rest-design/server.go
// 一句话说明：REST 接口设计规范落地。本文件演示"资源 + 方法语义"六条核心纪律：
// ① 资源名词复数进路径、动词交给 HTTP 方法；② POST 创建 201+Location；
// ③ GET 幂等只读；④ PUT 全量替换（缺字段落零值）；⑤ PATCH 部分更新（只动给出的字段）；
// ⑥ DELETE 幂等（不存在也 204）。规则集中在方法语义而不是 URL 动词上（主文档 3.1）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18101
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"errors"
	"net/http"
	"strings"
)

// Server 是 REST 服务的 handler 集合。依赖只收最简形态的 Store。
type Server struct {
	store *Store
}

// Register 把 REST 资源路由挂到 mux 上。Go 1.22+ 的方法路由模式让
// "路径 + HTTP 方法"写在同一条规则里——方法语义因此是路由的一等公民。
func (s *Server) Register(mux *http.ServeMux) {
	mux.HandleFunc("GET /v1/devices", s.handleList)
	mux.HandleFunc("POST /v1/devices", s.handleCreate)
	mux.HandleFunc("GET /v1/devices/{id}", s.handleGet)
	mux.HandleFunc("PUT /v1/devices/{id}", s.handleReplace)
	mux.HandleFunc("PATCH /v1/devices/{id}", s.handlePatch)
	mux.HandleFunc("DELETE /v1/devices/{id}", s.handleDelete)
}

func (s *Server) handleList(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, s.store.List())
}

func (s *Server) handleCreate(w http.ResponseWriter, r *http.Request) {
	var req createRequest
	if !decodeBody(w, r, &req) {
		return
	}
	name := strings.TrimSpace(req.Name)
	if name == "" {
		writeError(w, http.StatusBadRequest, "BAD_REQUEST", "name is required")
		return
	}
	d := s.store.Create(name)
	w.Header().Set("Location", "/v1/devices/"+d.ID) // 201 惯例：Location 指向新资源
	writeJSON(w, http.StatusCreated, d)
}

func (s *Server) handleGet(w http.ResponseWriter, r *http.Request) {
	d, err := s.store.Get(r.PathValue("id"))
	if err != nil {
		if errors.Is(err, ErrNotFound) {
			writeError(w, http.StatusNotFound, "DEVICE_NOT_FOUND", "device not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "INTERNAL", "internal error")
		return
	}
	writeJSON(w, http.StatusOK, d)
}

// handleReplace PUT 全量替换：请求体是完整表示。与 PATCH 的差异见文件头与主文档 3.1 表格。
func (s *Server) handleReplace(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Name   string `json:"name"`
		Online bool   `json:"online"`
	}
	if !decodeBody(w, r, &req) {
		return
	}
	id := r.PathValue("id")
	if _, err := s.store.Get(id); err != nil {
		if errors.Is(err, ErrNotFound) {
			writeError(w, http.StatusNotFound, "DEVICE_NOT_FOUND", "device not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "INTERNAL", "internal error")
		return
	}
	// PUT 语义：body 缺的字段落零值——"online" 不传就变成 false，这与 PATCH 相反。
	s.store.Replace(id, Device{Name: req.Name, Online: req.Online})
	writeJSON(w, http.StatusOK, s.mustGet(id))
}

// handlePatch PATCH 部分更新：指针字段区分"没传"与"传了 false/null"，只更新给出的字段。
func (s *Server) handlePatch(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Name   *string `json:"name"`
		Online *bool   `json:"online"`
	}
	if !decodeBody(w, r, &req) {
		return
	}
	id := r.PathValue("id")
	cur, err := s.store.Get(id)
	if err != nil {
		if errors.Is(err, ErrNotFound) {
			writeError(w, http.StatusNotFound, "DEVICE_NOT_FOUND", "device not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "INTERNAL", "internal error")
		return
	}
	if req.Name != nil {
		cur.Name = *req.Name
	}
	if req.Online != nil {
		cur.Online = *req.Online
	}
	s.store.Replace(id, cur) // 语义是"替换成更新后的完整状态"（读-改-写）
	writeJSON(w, http.StatusOK, cur)
}

func (s *Server) handleDelete(w http.ResponseWriter, r *http.Request) {
	// DELETE 幂等：资源已不存在也回 204——重复删除不应让客户端困惑（主文档 3.1）。
	_ = s.store.Delete(r.PathValue("id"))
	w.WriteHeader(http.StatusNoContent)
}

func (s *Server) mustGet(id string) Device {
	d, err := s.store.Get(id)
	if err != nil {
		panic(err) // 仅内部逻辑错误可达（刚 Replace 完必然存在），不是对外错误路径
	}
	return d
}
