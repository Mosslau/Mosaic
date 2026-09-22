// 来源：ph09-web-backend 阶段项目 —— 车辆数据上报 API（internal/api 包）
// 一句话说明：接口层 httptest 测试——认证换 token、列表/详情、上报全链路
// （鉴权/归属/校验/限流/404）、健康检查；错误结构断言。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./internal/api
//	go test -cover ./internal/api
//
// 验证状态：已验证（go1.25.6）
package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"tenetlang/go/ph09-web-backend/project/internal/vehicle"
)

const testSecret = "project-test-secret"

// newTestHandler 限流放开（1 分钟 100 次，测试不影响），种子 2 台车
func newTestHandler() http.Handler {
	store := vehicle.NewMemoryStore(
		vehicle.Vehicle{ID: "car-001", Status: "online", Speed: 60.5, Secret: "sec-1"},
		vehicle.Vehicle{ID: "car-002", Status: "offline", Speed: 0, Secret: "sec-2"},
	)
	return NewHandler(store, []byte(testSecret), 100, time.Minute)
}

func do(t *testing.T, h http.Handler, method, path, body, token string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

// deviceToken 辅助：认证换取 car-001 的 token
func deviceToken(t *testing.T, h http.Handler, deviceID, secret string) string {
	t.Helper()
	body := `{"device_id":"` + deviceID + `","secret":"` + secret + `"}`
	rec := do(t, h, "POST", "/api/devices/auth", body, "")
	if rec.Code != http.StatusOK {
		t.Fatalf("认证状态码 = %d, 期望 200, 响应: %s", rec.Code, rec.Body.String())
	}
	var resp struct {
		Token string `json:"token"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("认证响应解析失败: %v", err)
	}
	if resp.Token == "" {
		t.Fatal("认证响应缺少 token")
	}
	return resp.Token
}

func TestHealthz(t *testing.T) {
	rec := do(t, newTestHandler(), "GET", "/healthz", "", "")
	if rec.Code != http.StatusOK || rec.Body.String() != "ok" {
		t.Errorf("healthz = %d %q, 期望 200 ok", rec.Code, rec.Body.String())
	}
}

func TestDeviceAuth(t *testing.T) {
	h := newTestHandler()
	rec := do(t, h, "POST", "/api/devices/auth", `{"device_id":"car-001","secret":"sec-1"}`, "")
	if rec.Code != http.StatusOK {
		t.Errorf("正确密钥状态码 = %d, 期望 200", rec.Code)
	}
	recBad := do(t, h, "POST", "/api/devices/auth", `{"device_id":"car-001","secret":"wrong"}`, "")
	if recBad.Code != http.StatusUnauthorized {
		t.Errorf("错误密钥状态码 = %d, 期望 401", recBad.Code)
	}
	recEmpty := do(t, h, "POST", "/api/devices/auth", `{}`, "")
	if recEmpty.Code != http.StatusBadRequest {
		t.Errorf("缺字段状态码 = %d, 期望 400", recEmpty.Code)
	}
}

func TestListAndGet(t *testing.T) {
	h := newTestHandler()
	if rec := do(t, h, "GET", "/api/devices", "", ""); rec.Code != http.StatusOK {
		t.Errorf("列表状态码 = %d, 期望 200", rec.Code)
	}
	if rec := do(t, h, "GET", "/api/devices?status=broken", "", ""); rec.Code != http.StatusBadRequest {
		t.Errorf("非法状态值 = %d, 期望 400", rec.Code)
	}
	if rec := do(t, h, "GET", "/api/devices/car-001", "", ""); rec.Code != http.StatusOK {
		t.Errorf("详情状态码 = %d, 期望 200", rec.Code)
	}
	if rec := do(t, h, "GET", "/api/devices/nope", "", ""); rec.Code != http.StatusNotFound {
		t.Errorf("不存在状态码 = %d, 期望 404", rec.Code)
	}
}

func TestReportFlow(t *testing.T) {
	h := newTestHandler()
	token := deviceToken(t, h, "car-001", "sec-1")

	// 无 token → 401
	if rec := do(t, h, "POST", "/api/devices/car-001/report", `{"speed":80,"lat":31.2,"lng":121.5}`, ""); rec.Code != http.StatusUnauthorized {
		t.Errorf("无 token 上报状态码 = %d, 期望 401", rec.Code)
	}
	// 坏 token → 401
	if rec := do(t, h, "POST", "/api/devices/car-001/report", `{"speed":80,"lat":31.2,"lng":121.5}`, "garbage"); rec.Code != http.StatusUnauthorized {
		t.Errorf("坏 token 上报状态码 = %d, 期望 401", rec.Code)
	}
	// 归属不一致（car-001 的 token 上报 car-002）→ 403
	if rec := do(t, h, "POST", "/api/devices/car-002/report", `{"speed":80,"lat":31.2,"lng":121.5}`, token); rec.Code != http.StatusForbidden {
		t.Errorf("归属不一致上报状态码 = %d, 期望 403", rec.Code)
	}
	// 速度超范围 → 400
	if rec := do(t, h, "POST", "/api/devices/car-001/report", `{"speed":301,"lat":31.2,"lng":121.5}`, token); rec.Code != http.StatusBadRequest {
		t.Errorf("非法速度状态码 = %d, 期望 400", rec.Code)
	}
	// 纬度超范围 → 400
	if rec := do(t, h, "POST", "/api/devices/car-001/report", `{"speed":80,"lat":91,"lng":121.5}`, token); rec.Code != http.StatusBadRequest {
		t.Errorf("非法纬度状态码 = %d, 期望 400", rec.Code)
	}
	// 正常上报 → 200，车辆状态更新为 online、速度更新
	rec := do(t, h, "POST", "/api/devices/car-001/report", `{"speed":88.5,"lat":31.2,"lng":121.5}`, token)
	if rec.Code != http.StatusOK {
		t.Fatalf("正常上报状态码 = %d, 期望 200, 响应: %s", rec.Code, rec.Body.String())
	}
	var v vehicle.Vehicle
	if err := json.Unmarshal(rec.Body.Bytes(), &v); err != nil {
		t.Fatalf("上报响应解析失败: %v", err)
	}
	if v.Speed != 88.5 || v.Status != "online" {
		t.Errorf("上报后车辆 = %+v, 期望 speed=88.5 status=online", v)
	}
}

// TestReportRateLimit 每设备限流：窗口内超过 N 次返回 429（用极小 limit 验证）
func TestReportRateLimit(t *testing.T) {
	store := vehicle.NewMemoryStore(
		vehicle.Vehicle{ID: "car-001", Status: "online", Secret: "sec-1"},
	)
	h := NewHandler(store, []byte(testSecret), 3, time.Minute) // 每设备每分钟 3 次
	token := deviceToken(t, h, "car-001", "sec-1")

	statuses := make([]int, 0, 4)
	for i := 0; i < 4; i++ {
		rec := do(t, h, "POST", "/api/devices/car-001/report", `{"speed":80,"lat":31,"lng":121}`, token)
		statuses = append(statuses, rec.Code)
	}
	if statuses[2] != http.StatusOK {
		t.Errorf("第 3 次上报状态码 = %d, 期望 200（未超限）", statuses[2])
	}
	if statuses[3] != http.StatusTooManyRequests {
		t.Errorf("第 4 次上报状态码 = %d, 期望 429（超限）", statuses[3])
	}
}

// TestErrorStructure 错误体统一 {code, message}
func TestErrorStructure(t *testing.T) {
	h := newTestHandler()
	rec := do(t, h, "GET", "/api/devices/nope", "", "")
	var body map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("错误响应不是合法 JSON: %v", err)
	}
	if body["code"] != "NOT_FOUND" || body["message"] == "" {
		t.Errorf("错误体 = %v, 期望 code=NOT_FOUND 且 message 非空", body)
	}
}
