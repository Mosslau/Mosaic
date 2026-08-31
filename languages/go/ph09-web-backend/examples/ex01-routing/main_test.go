// 来源：09-web-backend.md 第 6 章示例 1 —— 路由与 JSON API
// 一句话说明：httptest 表驱动测试覆盖全部路由与错误路径（200/201/204/400/404/405/409）。
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

// do 辅助：构造请求并执行，返回 recorder
func do(t *testing.T, method, path, body string) *httptest.ResponseRecorder {
	t.Helper()
	var rdr *strings.Reader
	if body == "" {
		rdr = strings.NewReader("")
	} else {
		rdr = strings.NewReader(body)
	}
	req := httptest.NewRequest(method, path, rdr)
	rec := httptest.NewRecorder()
	newMux().ServeHTTP(rec, req)
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
		{"查询列表", "GET", "/devices", "", http.StatusOK},
		{"按状态过滤", "GET", "/devices?status=online", "", http.StatusOK},
		{"查询单个", "GET", "/devices/car-001", "", http.StatusOK},
		{"查询不存在", "GET", "/devices/nope", "", http.StatusNotFound},
		{"创建成功", "POST", "/devices", `{"id":"car-009","status":"online"}`, http.StatusCreated},
		{"创建重复 ID", "POST", "/devices", `{"id":"car-001","status":"online"}`, http.StatusConflict},
		{"创建缺 id", "POST", "/devices", `{"status":"online"}`, http.StatusBadRequest},
		{"创建非法状态", "POST", "/devices", `{"id":"x","status":"broken"}`, http.StatusBadRequest},
		{"创建非法 JSON", "POST", "/devices", `{oops`, http.StatusBadRequest},
		{"删除成功", "DELETE", "/devices/car-001", "", http.StatusNoContent},
		{"删除不存在", "DELETE", "/devices/nope", "", http.StatusNotFound},
		{"方法不允许", "PUT", "/devices/car-001", "", http.StatusMethodNotAllowed},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			rec := do(t, tc.method, tc.path, tc.body)
			if rec.Code != tc.wantStatus {
				t.Errorf("%s %s 状态码 = %d, 期望 %d, 响应体: %s",
					tc.method, tc.path, rec.Code, tc.wantStatus, rec.Body.String())
			}
		})
	}
}

// TestErrorBody 断言错误结构是 {code, message} 且 code 是稳定枚举
func TestErrorBody(t *testing.T) {
	rec := do(t, "GET", "/devices/nope", "")
	var body map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("错误响应不是合法 JSON: %v", err)
	}
	if body["code"] != "NOT_FOUND" {
		t.Errorf("code = %q, 期望 NOT_FOUND", body["code"])
	}
	if body["message"] == "" {
		t.Error("message 不应为空")
	}
}

// TestMethodNotAllowedAllowHeader 验证 405 时 ServeMux 自动带 Allow 头
func TestMethodNotAllowedAllowHeader(t *testing.T) {
	rec := do(t, "PUT", "/devices/car-001", "")
	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("状态码 = %d, 期望 405", rec.Code)
	}
	if allow := rec.Header().Get("Allow"); !strings.Contains(allow, "GET") {
		t.Errorf("Allow 头 = %q, 期望包含 GET", allow)
	}
}
