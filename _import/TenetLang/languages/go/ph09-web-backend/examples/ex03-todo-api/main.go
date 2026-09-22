// 来源：09-web-backend.md 第 6 章示例 3 —— Todo API（JSON 请求响应 + 校验 + 统一错误）
// 一句话说明：GET/POST/PUT/PATCH/DELETE 五方法完整 CRUD，内存切片存储 + Mutex，
// 手写参数校验，全部错误走统一 {code, message} 结构——handler 四段式（解析→校验→业务→响应）。
// 验证环境：go1.25.6（darwin/arm64），仅标准库
// 运行：
//
//	go run .
//	curl -s http://127.0.0.1:18080/todos
//	curl -s -X POST http://127.0.0.1:18080/todos -d '{"text":"写周报"}'
//	curl -s -X PATCH http://127.0.0.1:18080/todos/1/done
//
// 测试：
//
//	go test -v ./...
//	go test -cover ./...
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"strconv"
	"sync"
)

// Todo 待办项
type Todo struct {
	ID   int    `json:"id"`
	Text string `json:"text"`
	Done bool   `json:"done"`
}

// store 内存存储：Mutex 保护共享切片（ph06 并发安全落地）
type store struct {
	mu    sync.Mutex
	next  int
	todos []Todo
}

func newStore() *store {
	return &store{next: 1}
}

func (s *store) list() []Todo {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]Todo, len(s.todos))
	copy(out, s.todos) // 拷贝返回，防调用方修改内部状态
	return out
}

func (s *store) create(text string) (Todo, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	t := Todo{ID: s.next, Text: text}
	s.next++
	s.todos = append(s.todos, t)
	return t, nil
}

func (s *store) markDone(id int) (Todo, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	for i := range s.todos {
		if s.todos[i].ID == id {
			s.todos[i].Done = true
			return s.todos[i], nil
		}
	}
	return Todo{}, errors.New("not found")
}

func (s *store) update(id int, text string) (Todo, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	for i := range s.todos {
		if s.todos[i].ID == id {
			s.todos[i].Text = text
			return s.todos[i], nil
		}
	}
	return Todo{}, errors.New("not found")
}

func (s *store) remove(id int) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	for i := range s.todos {
		if s.todos[i].ID == id {
			s.todos = append(s.todos[:i], s.todos[i+1:]...)
			return nil
		}
	}
	return errors.New("not found")
}

func main() {
	addr := "127.0.0.1:18080"
	log.Printf("Todo API 监听 http://%s", addr)
	if err := http.ListenAndServe(addr, newMux(newStore())); err != nil {
		log.Fatal(err)
	}
}

// newMux 组装路由（store 依赖注入，测试可换实现）
func newMux(s *store) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /todos", handleList(s))
	mux.HandleFunc("POST /todos", handleCreate(s))
	mux.HandleFunc("PATCH /todos/{id}/done", handleMarkDone(s))
	mux.HandleFunc("PUT /todos/{id}", handleUpdate(s))
	mux.HandleFunc("DELETE /todos/{id}", handleDelete(s))
	return mux
}

func handleList(s *store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, s.list())
	}
}

// handleCreate 四段式：解析 → 校验 → 业务 → 响应
func handleCreate(s *store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Text string `json:"text"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil { // 解析
			writeError(w, http.StatusBadRequest, "INVALID_JSON", "请求体不是合法 JSON")
			return
		}
		if req.Text == "" { // 校验：必填（手写，标准库无声明式 validator）
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "text 不能为空")
			return
		}
		if len([]rune(req.Text)) > 100 { // 校验：长度上限
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "text 不能超过 100 个字符")
			return
		}
		t, err := s.create(req.Text) // 业务
		if err != nil {
			writeError(w, http.StatusInternalServerError, "INTERNAL", "创建失败")
			return
		}
		writeJSON(w, http.StatusCreated, t) // 响应：201
	}
}

func handleMarkDone(s *store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, err := parseID(r)
		if err != nil {
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "id 必须是正整数")
			return
		}
		t, err := s.markDone(id)
		if err != nil {
			writeError(w, http.StatusNotFound, "NOT_FOUND", "todo 不存在: "+strconv.Itoa(id))
			return
		}
		writeJSON(w, http.StatusOK, t)
	}
}

func handleUpdate(s *store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, err := parseID(r)
		if err != nil {
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "id 必须是正整数")
			return
		}
		var req struct {
			Text string `json:"text"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeError(w, http.StatusBadRequest, "INVALID_JSON", "请求体不是合法 JSON")
			return
		}
		if req.Text == "" {
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "text 不能为空")
			return
		}
		t, err := s.update(id, req.Text)
		if err != nil {
			writeError(w, http.StatusNotFound, "NOT_FOUND", "todo 不存在: "+strconv.Itoa(id))
			return
		}
		writeJSON(w, http.StatusOK, t)
	}
}

func handleDelete(s *store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, err := parseID(r)
		if err != nil {
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "id 必须是正整数")
			return
		}
		if err := s.remove(id); err != nil {
			writeError(w, http.StatusNotFound, "NOT_FOUND", "todo 不存在: "+strconv.Itoa(id))
			return
		}
		w.WriteHeader(http.StatusNoContent) // 204
	}
}

// parseID 解析路径参数 {id}：strconv.Atoi + 正整数判断（手写校验示例）
func parseID(r *http.Request) (int, error) {
	id, err := strconv.Atoi(r.PathValue("id"))
	if err != nil || id < 1 {
		return 0, errors.New("id 必须是正整数")
	}
	return id, nil
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		log.Printf("响应编码失败: %v", err)
	}
}

func writeError(w http.ResponseWriter, status int, code, msg string) {
	writeJSON(w, status, map[string]string{"code": code, "message": msg})
}
