// 来源：exercises/README.md 练习 3 参考实现 —— handler 单元测试（httptest，不真正起端口）
// 一句话说明：表驱动 + httptest.NewRecorder 断言状态码、Content-Type 与响应体。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	go test -v
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func testDevices() map[string]Device {
	return map[string]Device{
		"car-001": {ID: "car-001", Status: "online", Speed: 60.5},
	}
}

func TestDevicesAPI(t *testing.T) {
	mux := newMux(testDevices())
	cases := []struct {
		name       string
		method     string
		path       string
		wantStatus int
	}{
		{"列表", http.MethodGet, "/devices", http.StatusOK},
		{"单查命中", http.MethodGet, "/devices/car-001", http.StatusOK},
		{"单查未命中", http.MethodGet, "/devices/none", http.StatusNotFound},
		{"方法不允许", http.MethodPost, "/devices", http.StatusMethodNotAllowed},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequest(tc.method, tc.path, nil)
			rec := httptest.NewRecorder()
			mux.ServeHTTP(rec, req)
			if rec.Code != tc.wantStatus {
				t.Fatalf("%s %s: 状态码 = %d, 期望 %d", tc.method, tc.path, rec.Code, tc.wantStatus)
			}
			if ct := rec.Header().Get("Content-Type"); ct != "application/json; charset=utf-8" {
				t.Errorf("Content-Type = %q, 期望 application/json; charset=utf-8", ct)
			}
		})
	}
}

// TestGetDeviceBody 单独验证响应体内容可正确解码
func TestGetDeviceBody(t *testing.T) {
	mux := newMux(testDevices())
	req := httptest.NewRequest(http.MethodGet, "/devices/car-001", nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	var d Device
	if err := json.Unmarshal(rec.Body.Bytes(), &d); err != nil {
		t.Fatalf("响应体不是合法 JSON: %v", err)
	}
	if d.ID != "car-001" || d.Status != "online" {
		t.Errorf("响应体 = %+v, 期望 car-001/online", d)
	}
}
