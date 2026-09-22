// 来源：ph09-web-backend 练习 1 参考实现 —— Todo API
// 一句话说明：httptest 表驱动覆盖全部路由与错误路径（200/201/204/400/404/405）+ done 过滤行为。
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
	"testing"
)

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
		{"列出已完成过滤", "GET", "/todos?done=true", "", http.StatusOK},
		{"查询单个", "GET", "/todos/1", "", http.StatusOK},
		{"查询不存在", "GET", "/todos/99", "", http.StatusNotFound},
		{"查询非法 id", "GET", "/todos/abc", "", http.StatusBadRequest},
		{"创建成功", "POST", "/todos", `{"text":"新任务"}`, http.StatusCreated},
		{"创建空文本", "POST", "/todos", `{"text":""}`, http.StatusBadRequest},
		{"创建超长文本", "POST", "/todos", `{"text":"` + strings.Repeat("长", 101) + `"}`, http.StatusBadRequest},
		{"创建非法 JSON", "POST", "/todos", `{oops`, http.StatusBadRequest},
		{"标记完成", "PATCH", "/todos/1/done", "", http.StatusOK},
		{"标记不存在", "PATCH", "/todos/99/done", "", http.StatusNotFound},
		{"更新", "PUT", "/todos/1", `{"text":"改名"}`, http.StatusOK},
		{"更新不存在", "PUT", "/todos/99", `{"text":"x"}`, http.StatusNotFound},
		{"删除成功", "DELETE", "/todos/1", "", http.StatusNoContent},
		{"删除不存在", "DELETE", "/todos/99", "", http.StatusNotFound},
		{"方法不允许", "PUT", "/todos/1/done", "", http.StatusMethodNotAllowed},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			h := newMux(newTestStore()) // 每用例独立 store，避免状态污染
			rec := do(t, h, tc.method, tc.path, tc.body)
			if rec.Code != tc.wantStatus {
				t.Errorf("%s %s 状态码 = %d, 期望 %d, 响应体: %s",
					tc.method, tc.path, rec.Code, tc.wantStatus, rec.Body.String())
			}
		})
	}
}

// TestDoneFilter 标记完成后 ?done=true 能过滤出来
func TestDoneFilter(t *testing.T) {
	h := newMux(newTestStore())
	do(t, h, "PATCH", "/todos/1/done", "")

	rec := do(t, h, "GET", "/todos?done=true", "")
	var todos []Todo
	if err := json.Unmarshal(rec.Body.Bytes(), &todos); err != nil {
		t.Fatalf("JSON 解析失败: %v", err)
	}
	if len(todos) != 1 || !todos[0].Done {
		t.Errorf("done=true 过滤结果 = %+v, 期望只含 1 条已完成", todos)
	}
}

// TestErrorBody 错误结构统一 {code, message}
func TestErrorBody(t *testing.T) {
	h := newMux(newTestStore())
	rec := do(t, h, "GET", "/todos/99", "")
	var body map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("错误响应不是合法 JSON: %v", err)
	}
	if body["code"] != "NOT_FOUND" || body["message"] == "" {
		t.Errorf("错误体 = %v, 期望 code=NOT_FOUND 且 message 非空", body)
	}
}
