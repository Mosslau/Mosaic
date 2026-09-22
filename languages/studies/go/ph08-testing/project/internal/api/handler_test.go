// 来源：ph08-testing 阶段项目 —— 带测试的设备管理 HTTP API
// 一句话说明：httptest 表驱动测试覆盖全部路由与错误路径，附 benchmark。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./internal/api
//	go test -cover ./internal/api
//	go test -bench=. -benchmem -run=^$ ./internal/api
//
// 验证状态：已验证（go1.25.6）
package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"tenetlang/go/ph08-testing/project/internal/device"
)

// newTestHandler 辅助：带一条种子数据的 handler；t.Helper 让失败定位到调用处
func newTestHandler(t *testing.T) http.Handler {
	t.Helper()
	return NewHandler(device.NewMemoryStore(device.Device{ID: "car-001", Status: "online"}))
}

func do(t *testing.T, h http.Handler, method, path, body string) *httptest.ResponseRecorder {
	t.Helper()
	var rdr *strings.Reader
	if body == "" {
		rdr = strings.NewReader("")
	} else {
		rdr = strings.NewReader(body)
	}
	req := httptest.NewRequest(method, path, rdr)
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
		{"查询列表", "GET", "/devices", "", http.StatusOK},
		{"查询单个", "GET", "/devices/car-001", "", http.StatusOK},
		{"查询不存在", "GET", "/devices/nope", "", http.StatusNotFound},
		{"创建成功", "POST", "/devices", `{"id":"car-002","status":"offline"}`, http.StatusCreated},
		{"创建重复 ID", "POST", "/devices", `{"id":"car-001","status":"x"}`, http.StatusConflict},
		{"创建缺字段", "POST", "/devices", `{"id":""}`, http.StatusBadRequest},
		{"创建非法 JSON", "POST", "/devices", `{oops`, http.StatusBadRequest},
		{"删除成功", "DELETE", "/devices/car-001", "", http.StatusNoContent},
		{"删除不存在", "DELETE", "/devices/nope", "", http.StatusNotFound},
		{"方法不允许", "PUT", "/devices/car-001", "", http.StatusMethodNotAllowed},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			// 每个用例独立 handler：避免创建/删除用例互相污染状态
			h := newTestHandler(t)
			rec := do(t, h, tc.method, tc.path, tc.body)
			if rec.Code != tc.wantStatus {
				t.Errorf("%s %s 状态码 = %d, 期望 %d, 响应体: %s",
					tc.method, tc.path, rec.Code, tc.wantStatus, rec.Body.String())
			}
		})
	}
}

// TestGetDeviceBody 深入断言响应体字段（状态码之外的第二重断言）
func TestGetDeviceBody(t *testing.T) {
	h := newTestHandler(t)
	rec := do(t, h, "GET", "/devices/car-001", "")

	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type = %q, 期望 application/json", ct)
	}
	var got device.Device
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("JSON 解析失败: %v", err)
	}
	if got.ID != "car-001" || got.Status != "online" {
		t.Errorf("响应 = %+v, 期望 car-001/online", got)
	}
}

// TestCreateThenGet 行为链路：创建后能查到
func TestCreateThenGet(t *testing.T) {
	h := newTestHandler(t)
	do(t, h, "POST", "/devices", `{"id":"car-009","status":"charging"}`)

	rec := do(t, h, "GET", "/devices/car-009", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("创建后查询状态码 = %d, 期望 200", rec.Code)
	}
	var got device.Device
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("JSON 解析失败: %v", err)
	}
	if got.Status != "charging" {
		t.Errorf("status = %q, 期望 charging", got.Status)
	}
}

var sinkRecorder *httptest.ResponseRecorder

func BenchmarkGetDevice(b *testing.B) {
	h := NewHandler(device.NewMemoryStore(device.Device{ID: "car-001", Status: "online"}))
	req := httptest.NewRequest(http.MethodGet, "/devices/car-001", nil)
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		sinkRecorder = rec
	}
}
