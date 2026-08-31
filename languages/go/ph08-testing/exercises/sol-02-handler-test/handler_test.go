// 来源：ph08-testing 练习 2 参考实现 —— 给 handler 写测试
// 一句话说明：httptest.NewRequest + NewRecorder，覆盖 200 / 404 / 405 三条路径。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

// doRequest 辅助：发请求并返回 recorder；t.Helper 让失败定位到调用处
func doRequest(t *testing.T, h http.Handler, method, path string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(method, path, nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func TestGetDeviceOK(t *testing.T) {
	h := NewHandler(map[string]Device{"car-001": {ID: "car-001", Status: "online"}})
	rec := doRequest(t, h, http.MethodGet, "/devices/car-001")

	if rec.Code != http.StatusOK {
		t.Fatalf("状态码 = %d, 期望 %d", rec.Code, http.StatusOK)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type = %q, 期望 application/json", ct)
	}
	var got Device
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("JSON 解析失败: %v", err)
	}
	if got.ID != "car-001" || got.Status != "online" {
		t.Errorf("响应 = %+v, 期望 car-001/online", got)
	}
}

func TestGetDeviceNotFound(t *testing.T) {
	h := NewHandler(map[string]Device{})
	rec := doRequest(t, h, http.MethodGet, "/devices/nope")

	if rec.Code != http.StatusNotFound {
		t.Fatalf("状态码 = %d, 期望 %d", rec.Code, http.StatusNotFound)
	}
	var body map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("JSON 解析失败: %v", err)
	}
	if body["error"] == "" {
		t.Error("错误响应缺少 error 字段")
	}
}

func TestMethodNotAllowed(t *testing.T) {
	h := NewHandler(map[string]Device{"car-001": {ID: "car-001", Status: "online"}})
	rec := doRequest(t, h, http.MethodPost, "/devices/car-001")

	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("状态码 = %d, 期望 %d", rec.Code, http.StatusMethodNotAllowed)
	}
}
