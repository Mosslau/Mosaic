// 来源：ph08-testing 主文档示例 2 —— HTTP handler 测试（httptest + 断言 JSON）
// 一句话说明：httptest.NewRequest + NewRecorder，不起端口验证状态码与 JSON 响应。
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

func TestGetDevice(t *testing.T) {
	h := NewHandler(map[string]Device{"car-001": {ID: "car-001", Status: "online"}})
	req := httptest.NewRequest(http.MethodGet, "/devices/car-001", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("状态码 = %d, 期望 %d", rec.Code, http.StatusOK)
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
	req := httptest.NewRequest(http.MethodGet, "/devices/nope", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Fatalf("状态码 = %d, 期望 404", rec.Code)
	}
	var body map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("JSON 解析失败: %v", err)
	}
	if body["error"] == "" {
		t.Error("错误响应缺少 error 字段")
	}
}

// TestMethodNotAllowed：Go 1.22 路由注册 "GET /devices/{id}" 后，
// 其他方法访问同路径自动返回 405（无需手写方法校验）
func TestMethodNotAllowed(t *testing.T) {
	h := NewHandler(map[string]Device{})
	req := httptest.NewRequest(http.MethodPost, "/devices/car-001", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("状态码 = %d, 期望 405", rec.Code)
	}
}
