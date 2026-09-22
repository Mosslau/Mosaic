package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"tenetlang/go/ph10-database/project/internal/cache"
	"tenetlang/go/ph10-database/project/internal/store"
)

// newTestService 用临时 SQLite 库 + 内存缓存构造完整服务（不依赖 Redis）
func newTestService(t *testing.T) http.Handler {
	t.Helper()
	s, err := store.Open(filepath.Join(t.TempDir(), "api.db"))
	if err != nil {
		t.Fatalf("store.Open: %v", err)
	}
	t.Cleanup(func() { s.Close() })
	svc := NewService(s, cache.NewMemory())
	return NewHandler(svc)
}

func doJSON(t *testing.T, h http.Handler, method, path, body string) *httptest.ResponseRecorder {
	t.Helper()
	var r *http.Request
	if body == "" {
		r = httptest.NewRequest(method, path, nil)
	} else {
		r = httptest.NewRequest(method, path, bytes.NewBufferString(body))
	}
	r.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, r)
	return rec
}

func TestHealthz(t *testing.T) {
	h := newTestService(t)
	rec := doJSON(t, h, "GET", "/healthz", "")
	if rec.Code != http.StatusOK || rec.Body.String() != "ok" {
		t.Errorf("healthz = %d %q", rec.Code, rec.Body.String())
	}
}

func TestReportAndLatest(t *testing.T) {
	h := newTestService(t)
	body := `{"points":[
		{"lat":31.1,"lng":121.2,"speed":60,"ts":"2025-01-01T00:00:00Z"},
		{"lat":31.2,"lng":121.3,"speed":70,"ts":"2025-01-01T00:01:00Z"}
	]}`
	rec := doJSON(t, h, "POST", "/api/devices/car-001/points", body)
	if rec.Code != http.StatusCreated {
		t.Fatalf("report = %d, want 201: %s", rec.Code, rec.Body.String())
	}
	var inserted map[string]any
	json.Unmarshal(rec.Body.Bytes(), &inserted)
	if inserted["inserted"] != float64(2) {
		t.Errorf("inserted = %v, want 2", inserted["inserted"])
	}
	// 最新位置：走缓存命中（report 时已回填）
	rec = doJSON(t, h, "GET", "/api/devices/car-001/latest", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("latest = %d, want 200", rec.Code)
	}
	var latest cache.Entry
	json.Unmarshal(rec.Body.Bytes(), &latest)
	if latest.Speed != 70 || latest.DeviceID != "car-001" {
		t.Errorf("latest = %+v, want 70/car-001", latest)
	}
}

func TestReportValidation(t *testing.T) {
	h := newTestService(t)
	cases := []struct {
		name string
		body string
		want int
	}{
		{"空 points", `{"points":[]}`, 400},
		{"非法坐标", `{"points":[{"lat":91,"lng":0,"speed":1,"ts":"2025-01-01T00:00:00Z"}]}`, 400},
		{"超速", `{"points":[{"lat":0,"lng":0,"speed":301,"ts":"2025-01-01T00:00:00Z"}]}`, 400},
		{"坏时间", `{"points":[{"lat":0,"lng":0,"speed":1,"ts":"not-a-time"}]}`, 400},
		{"坏 JSON", `{not-json`, 400},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			rec := doJSON(t, h, "POST", "/api/devices/car-001/points", c.body)
			if rec.Code != c.want {
				t.Errorf("code = %d, want %d: %s", rec.Code, c.want, rec.Body.String())
			}
		})
	}
}

func TestLatestNotFound(t *testing.T) {
	h := newTestService(t)
	rec := doJSON(t, h, "GET", "/api/devices/ghost/latest", "")
	if rec.Code != http.StatusNotFound {
		t.Errorf("latest = %d, want 404", rec.Code)
	}
}

func TestTrajectory(t *testing.T) {
	h := newTestService(t)
	body := `{"points":[
		{"lat":31.0,"lng":121.0,"speed":50,"ts":"2025-01-01T00:00:00Z"},
		{"lat":31.1,"lng":121.1,"speed":55,"ts":"2025-01-01T00:05:00Z"},
		{"lat":31.2,"lng":121.2,"speed":60,"ts":"2025-01-01T00:10:00Z"}
	]}`
	if rec := doJSON(t, h, "POST", "/api/devices/car-001/points", body); rec.Code != 201 {
		t.Fatalf("seed report = %d", rec.Code)
	}
	// 3~8 分钟区间 → 只有 55 那一条
	rec := doJSON(t, h, "GET", "/api/devices/car-001/trajectory?from=2025-01-01T00:03:00Z&to=2025-01-01T00:08:00Z", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("trajectory = %d, want 200", rec.Code)
	}
	var points []store.Point
	json.Unmarshal(rec.Body.Bytes(), &points)
	if len(points) != 1 || points[0].Speed != 55 {
		t.Errorf("points = %+v, want 只有 55 那一条", points)
	}
	// 参数校验
	if rec := doJSON(t, h, "GET", "/api/devices/car-001/trajectory?from=bad&to=2025-01-01T00:08:00Z", ""); rec.Code != 400 {
		t.Error("坏 from 应 400")
	}
	if rec := doJSON(t, h, "GET", "/api/devices/car-001/trajectory?from=2025-01-01T00:08:00Z&to=2025-01-01T00:03:00Z", ""); rec.Code != 400 {
		t.Error("from 晚于 to 应 400")
	}
}

func TestRouteMethodNotAllowed(t *testing.T) {
	h := newTestService(t)
	// GET 打 POST 路由 → 405（Go 1.22 ServeMux 自动处理 + Allow 头）
	rec := doJSON(t, h, "GET", "/api/devices/car-001/points", "")
	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("code = %d, want 405", rec.Code)
	}
}
