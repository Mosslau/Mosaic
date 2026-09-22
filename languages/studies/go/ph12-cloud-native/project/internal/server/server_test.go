package server

import (
	"io"
	"log/slog"
	"net"
	"net/http"
	"strings"
	"testing"
)

// newTest 起真实 server（随机端口），返回 baseURL、stop、*Server（控制 ready）
func newTest(t *testing.T) (string, func(), *Server) {
	t.Helper()
	logger := slog.New(slog.NewJSONHandler(io.Discard, nil))
	srv := New(logger, NewMetrics())
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	httpSrv := &http.Server{Handler: srv.Handler()}
	go func() { _ = httpSrv.Serve(ln) }()
	return "http://" + ln.Addr().String(), func() { _ = httpSrv.Close() }, srv
}

func get(t *testing.T, url string) (int, string) {
	t.Helper()
	resp, err := http.Get(url)
	if err != nil {
		t.Fatalf("GET %s: %v", url, err)
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, string(b)
}

func TestHealthz(t *testing.T) {
	base, stop, _ := newTest(t)
	defer stop()
	code, body := get(t, base+"/healthz")
	if code != http.StatusOK || !strings.Contains(body, "ok") {
		t.Fatalf("healthz = %d %s", code, body)
	}
}

// 就绪转换：未就绪 503 → MarkReady 后 200
func TestReadyzTransition(t *testing.T) {
	base, stop, srv := newTest(t)
	defer stop()

	code, body := get(t, base+"/readyz")
	if code != http.StatusServiceUnavailable || !strings.Contains(body, "not_ready") {
		t.Fatalf("未就绪: %d %s", code, body)
	}
	// 业务接口未就绪时 503
	code, _ = get(t, base+"/api/devices/d1")
	if code != http.StatusServiceUnavailable {
		t.Fatalf("业务未就绪: %d", code)
	}

	srv.MarkReady()
	code, body = get(t, base+"/readyz")
	if code != http.StatusOK || !strings.Contains(body, "ready") {
		t.Fatalf("就绪: %d %s", code, body)
	}
	code, body = get(t, base+"/api/devices/d1")
	if code != http.StatusOK || !strings.Contains(body, "d1") {
		t.Fatalf("业务就绪: %d %s", code, body)
	}
}

// SetReady(false) 优雅退出路径：/readyz 立即 503
func TestSetReadyFalse(t *testing.T) {
	base, stop, srv := newTest(t)
	defer stop()
	srv.MarkReady()
	code, _ := get(t, base+"/readyz")
	if code != http.StatusOK {
		t.Fatalf("就绪: %d", code)
	}
	srv.SetReady(false)
	code, _ = get(t, base+"/readyz")
	if code != http.StatusServiceUnavailable {
		t.Fatalf("摘流量后: %d, want 503", code)
	}
}

// /metrics 暴露完整 exposition（含 counter/gauge/histogram 与业务计数）
func TestMetricsExposition(t *testing.T) {
	base, stop, srv := newTest(t)
	defer stop()
	srv.MarkReady()
	// 触发 2 次成功请求 + 1 次缺 id 请求
	_, _ = get(t, base+"/api/devices/d1")
	_, _ = get(t, base+"/api/devices/d2")
	resp, err := http.Get(base + "/api/devices/")
	if err != nil {
		t.Fatalf("GET: %v", err)
	}
	_ = resp.Body.Close()

	_, text := get(t, base+"/metrics")
	for _, want := range []string{
		"# TYPE http_requests_total counter",
		"# TYPE http_requests_inflight gauge",
		"# TYPE http_request_duration_seconds histogram",
		"http_request_duration_seconds_count",
		`http_requests_total{handler="api"} 2`,
	} {
		if !strings.Contains(text, want) {
			t.Fatalf("/metrics 缺 %q:\n%s", want, text)
		}
	}
}

// 404：未注册路径
func TestUnknownPath(t *testing.T) {
	base, stop, _ := newTest(t)
	defer stop()
	code, _ := get(t, base+"/nope")
	if code != http.StatusNotFound {
		t.Fatalf("unknown = %d, want 404", code)
	}
}

// 指标注册表顺序稳定：两次渲染结果一致（Prometheus 抓取可 diff）
func TestRenderStable(t *testing.T) {
	m := NewMetrics()
	a := m.Registry.Render()
	b := m.Registry.Render()
	if a != b {
		t.Fatalf("渲染不稳定:\n---\n%s\n---\n%s", a, b)
	}
}
