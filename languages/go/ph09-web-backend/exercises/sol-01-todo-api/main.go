// 来源：ph09-web-backend 练习 1 参考实现 —— Todo API
// 一句话说明：map 存储 + RWMutex 的 Todo CRUD：列表（done 过滤）/单个/创建/标完成/改文本/删除，
// 统一错误 {code, message}，handler 四段式（解析→校验→业务→响应）。
// 验证环境：go1.25.6（darwin/arm64），仅标准库
// 运行：
//
//	go test -v ./...
//	go run .          # 监听 127.0.0.1:18080
//	curl -s -X POST http://127.0.0.1:18080/todos -d '{"text":"写周报"}'
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

// store 内存 map 存储：RWMutex——读多写少用 RWMutex 更合适（ph06 必会概念）
type store struct {
	mu    sync.RWMutex
	next  int
	items map[int]Todo
}

func newStore() *store {
	return &store{next: 1, items: make(map[int]Todo)}
}

func (s *store) list(doneOnly bool) []Todo {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]Todo, 0, len(s.items))
	for _, t := range s.items {
		if !doneOnly || t.Done {
			out = append(out, t)
		}
	}
	return out
}

func (s *store) get(id int) (Todo, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	t, ok := s.items[id]
	return t, ok
}

func (s *store) create(text string) Todo {
	s.mu.Lock()
	defer s.mu.Unlock()
	t := Todo{ID: s.next, Text: text}
	s.next++
	s.items[t.ID] = t
	return t
}

func (s *store) markDone(id int) (Todo, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	t, ok := s.items[id]
	if !ok {
		return Todo{}, errors.New("not found")
	}
	t.Done = true
	s.items[id] = t
	return t, nil
}

func (s *store) update(id int, text string) (Todo, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	t, ok := s.items[id]
	if !ok {
		return Todo{}, errors.New("not found")
	}
	t.Text = text
	s.items[id] = t
	return t, nil
}

func (s *store) remove(id int) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.items[id]; !ok {
		return errors.New("not found")
	}
	delete(s.items, id)
	return nil
}

func main() {
	addr := "127.0.0.1:18080"
	log.Printf("Todo API 监听 http://%s", addr)
	if err := http.ListenAndServe(addr, newMux(newStore())); err != nil {
		log.Fatal(err)
	}
}

func newMux(s *store) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /todos", handleList(s))
	mux.HandleFunc("GET /todos/{id}", handleGet(s))
	mux.HandleFunc("POST /todos", handleCreate(s))
	mux.HandleFunc("PATCH /todos/{id}/done", handleMarkDone(s))
	mux.HandleFunc("PUT /todos/{id}", handleUpdate(s))
	mux.HandleFunc("DELETE /todos/{id}", handleDelete(s))
	return mux
}

func handleList(s *store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		doneOnly := r.URL.Query().Get("done") == "true" // 其他值一律视为不过滤
		writeJSON(w, http.StatusOK, s.list(doneOnly))
	}
}

func handleGet(s *store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, err := parseID(r)
		if err != nil {
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", err.Error())
			return
		}
		t, ok := s.get(id)
		if !ok {
			writeError(w, http.StatusNotFound, "NOT_FOUND", "todo 不存在: "+strconv.Itoa(id))
			return
		}
		writeJSON(w, http.StatusOK, t)
	}
}

func handleCreate(s *store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
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
		if len([]rune(req.Text)) > 100 { // []rune 数长度：中文按 1 字符
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "text 不能超过 100 个字符")
			return
		}
		t := s.create(req.Text)
		writeJSON(w, http.StatusCreated, t) // 201
	}
}

func handleMarkDone(s *store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, err := parseID(r)
		if err != nil {
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", err.Error())
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
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", err.Error())
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
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", err.Error())
			return
		}
		if err := s.remove(id); err != nil {
			writeError(w, http.StatusNotFound, "NOT_FOUND", "todo 不存在: "+strconv.Itoa(id))
			return
		}
		w.WriteHeader(http.StatusNoContent) // 204
	}
}

// parseID 路径参数 {id} 必须是正整数
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
