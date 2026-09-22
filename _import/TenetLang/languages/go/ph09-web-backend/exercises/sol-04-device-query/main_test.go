// 来源：ph09-web-backend 练习 4 参考实现 —— 设备状态查询 API
// 一句话说明：表格驱动测试（ph08 风格）覆盖 200 / 400 / 404 / 405，含过滤数量断言。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...
//	go test -cover ./...
//
// 验证状态：已验证（go1.25.6，覆盖率 ≥ 80%）
package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func do(t *testing.T, method, path string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(method, path, nil)
	rec := httptest.NewRecorder()
	newMux().ServeHTTP(rec, req)
	return rec
}

func TestRoutes(t *testing.T) {
	cases := []struct {
		name       string
		method     string
		path       string
		wantStatus int
	}{
		{"列出全部", "GET", "/api/devices", http.StatusOK},
		{"过滤 online", "GET", "/api/devices?status=online", http.StatusOK},
		{"过滤 offline", "GET", "/api/devices?status=offline", http.StatusOK},
		{"非法状态值", "GET", "/api/devices?status=broken", http.StatusBadRequest},
		{"查询单个", "GET", "/api/devices/car-001", http.StatusOK},
		{"查询不存在", "GET", "/api/devices/nope", http.StatusNotFound},
		{"方法不允许", "POST", "/api/devices", http.StatusMethodNotAllowed},
		{"查询路径缺 id", "GET", "/api/devices/", http.StatusNotFound},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			rec := do(t, tc.method, tc.path)
			if rec.Code != tc.wantStatus {
				t.Errorf("%s %s 状态码 = %d, 期望 %d, 响应体: %s",
					tc.method, tc.path, rec.Code, tc.wantStatus, rec.Body.String())
			}
		})
	}
}

// TestFilterCount 过滤数量正确：online 2 台、offline 1 台
func TestFilterCount(t *testing.T) {
	rec := do(t, "GET", "/api/devices?status=online")
	var list []Device
	if err := json.Unmarshal(rec.Body.Bytes(), &list); err != nil {
		t.Fatalf("JSON 解析失败: %v", err)
	}
	if len(list) != 2 {
		t.Errorf("online 设备数 = %d, 期望 2", len(list))
	}
}

// TestGetDeviceBody 单个查询断言响应体字段
func TestGetDeviceBody(t *testing.T) {
	rec := do(t, "GET", "/api/devices/car-001")
	var d Device
	if err := json.Unmarshal(rec.Body.Bytes(), &d); err != nil {
		t.Fatalf("JSON 解析失败: %v", err)
	}
	if d.ID != "car-001" || d.Status != "online" || d.Speed != 60.5 {
		t.Errorf("设备 = %+v, 期望 car-001/online/60.5", d)
	}
}

// TestErrorBody 错误结构统一 {code, message}
func TestErrorBody(t *testing.T) {
	rec := do(t, "GET", "/api/devices/nope")
	var body map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("错误响应不是合法 JSON: %v", err)
	}
	if body["code"] != "NOT_FOUND" || body["message"] == "" {
		t.Errorf("错误体 = %v, 期望 code=NOT_FOUND 且 message 非空", body)
	}
}
