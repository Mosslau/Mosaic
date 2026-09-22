// 来源：09-web-backend.md 第 6 章示例 3 —— Todo API
// 一句话说明：httptest 覆盖五方法 CRUD 与错误路径（200/201/204/400/404/405），
// 每个用例独立 store 避免用例间状态污染。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...
//	go test -cover ./...
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
)

// newTestStore 带两条种子数据的 store
func newTestStore() *store {
	s := newStore()
	s.create("种子一")
	s.create("种子二")
	return s
}

func do(t *testing.T, h http.Handler, method, path, body string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func TestRoutes(t *testing.T) {
	cases := []struct {
		name       string
		method     string
		path       string
		body       string
		wantStatus int
	}{
		{"列出", "GET", "/todos", "", http.StatusOK},
		{"创建成功", "POST", "/todos", `{"text":"新任务"}`, http.StatusCreated},
		{"创建空文本", "POST", "/todos", `{"text":""}`, http.StatusBadRequest},
		{"创建非法 JSON", "POST", "/todos", `{oops`, http.StatusBadRequest},
		{"标记完成", "PATCH", "/todos/1/done", "", http.StatusOK},
		{"标记不存在", "PATCH", "/todos/99/done", "", http.StatusNotFound},
		{"标记非法 id", "PATCH", "/todos/abc/done", "", http.StatusBadRequest},
		{"更新", "PUT", "/todos/1", `{"text":"改名"}`, http.StatusOK},
		{"更新不存在", "PUT", "/todos/99", `{"text":"x"}`, http.StatusNotFound},
		{"删除成功", "DELETE", "/todos/1", "", http.StatusNoContent},
		{"删除不存在", "DELETE", "/todos/99", "", http.StatusNotFound},
		{"方法不允许", "GET", "/todos/1/done", "", http.StatusMethodNotAllowed},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			h := newMux(newTestStore()) // 每个用例独立 store：创建/删除用例不污染其他用例
			rec := do(t, h, tc.method, tc.path, tc.body)
			if rec.Code != tc.wantStatus {
				t.Errorf("%s %s 状态码 = %d, 期望 %d, 响应体: %s",
					tc.method, tc.path, rec.Code, tc.wantStatus, rec.Body.String())
			}
		})
	}
}

// TestCreateThenList 行为链路：创建后列表可见、字段正确
func TestCreateThenList(t *testing.T) {
	h := newMux(newTestStore())
	do(t, h, "POST", "/todos", `{"text":"写周报"}`)

	rec := do(t, h, "GET", "/todos", "")
	var todos []Todo
	if err := json.Unmarshal(rec.Body.Bytes(), &todos); err != nil {
		t.Fatalf("JSON 解析失败: %v", err)
	}
	if len(todos) != 3 {
		t.Fatalf("列表长度 = %d, 期望 3（种子 2 + 新建 1）", len(todos))
	}
	last := todos[len(todos)-1]
	if last.Text != "写周报" || last.Done {
		t.Errorf("最后一项 = %+v, 期望 text=写周报 且未完成", last)
	}
}

// TestErrorBody 错误结构统一为 {code, message}
func TestErrorBody(t *testing.T) {
	h := newMux(newTestStore())
	rec := do(t, h, "DELETE", "/todos/99", "")
	var body map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("错误响应不是合法 JSON: %v", err)
	}
	if body["code"] != "NOT_FOUND" || body["message"] == "" {
		t.Errorf("错误体 = %v, 期望 code=NOT_FOUND 且 message 非空", body)
	}
}

// TestStoreConcurrent 并发安全：100 个 goroutine 并发创建不丢数据（呼应 ph06）
func TestStoreConcurrent(t *testing.T) {
	s := newStore()
	const n = 100
	var wg sync.WaitGroup
	wg.Add(n)
	for i := 0; i < n; i++ {
		go func() {
			defer wg.Done()
			_, _ = s.create("任务")
		}()
	}
	wg.Wait()
	if got := len(s.list()); got != n {
		t.Errorf("并发创建后条数 = %d, 期望 %d", got, n)
	}
}
