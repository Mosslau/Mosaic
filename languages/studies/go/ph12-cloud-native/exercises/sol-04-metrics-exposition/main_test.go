package main

import (
	"bufio"
	"net"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"sync"
	"testing"
)

// 纯渲染测试：直查文本输出是否符合 exposition 语法
func TestExpositionFormat(t *testing.T) {
	reg := newRegistry()
	m := newAppMetrics()
	m.register(reg)

	m.reqTotal.Inc()
	m.reqTotal.Add(2) // 3
	m.inflight.Inc()
	m.inflight.Dec()
	m.latencyHist.Observe(0.001)
	m.latencyHist.Observe(0.02)
	m.latencyHist.Observe(2.0)

	text := reg.render()
	checks := []string{
		"# HELP http_requests_total Total HTTP requests processed.",
		"# TYPE http_requests_total counter",
		`http_requests_total{handler="api"} 3`,
		"http_requests_inflight 0",
		`http_request_duration_seconds_bucket{le="0.005"} 1`,
		`http_request_duration_seconds_bucket{le="0.05"} 2`,
		`http_request_duration_seconds_bucket{le="+Inf"} 3`,
		"http_request_duration_seconds_sum 2.021",
		"http_request_duration_seconds_count 3",
	}
	for _, want := range checks {
		if !strings.Contains(text, want) {
			t.Fatalf("缺 %q:\n%s", want, text)
		}
	}
}

// counter 只增不减；并发 +1/-1 后仍精确（-race 验证无数据竞争）
func TestCounterMonotonicAndConcurrent(t *testing.T) {
	c := newCounter("c_total", "h", nil)
	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); c.Inc() }()
	}
	wg.Wait()
	c.mu.Lock()
	if c.value != 50 {
		t.Fatalf("counter = %v, want 50", c.value)
	}
	c.mu.Unlock()
}

func TestLabelsSortedAndEscaped(t *testing.T) {
	var sb strings.Builder
	writeLabels(&sb, map[string]string{"zone": "b", "method": "GET"})
	if sb.String() != `{method="GET",zone="b"}` {
		t.Fatalf("标签排序错误: %s", sb.String())
	}
	sb.Reset()
	writeLabels(&sb, nil)
	if sb.String() != "" {
		t.Fatalf("空标签应无输出: %q", sb.String())
	}
	if escape(`a"b\c`) != `a\"b\\c` {
		t.Fatal("转义错误")
	}
}

func TestFormatFloat(t *testing.T) {
	if formatFloat(3) != "3" || formatFloat(2.5) != "2.5" {
		t.Fatal("formatFloat 异常")
	}
}

// 端到端：真实 server，发请求 → 抓 /metrics → 计数反映
func TestScrapeReflectsRequests(t *testing.T) {
	reg := newRegistry()
	m := newAppMetrics()
	m.register(reg)

	mux := http.NewServeMux()
	mux.HandleFunc("GET /metrics", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
		_, _ = w.Write([]byte(reg.render()))
	})
	mux.HandleFunc("GET /api/hello", func(w http.ResponseWriter, r *http.Request) {
		m.inflight.Inc()
		defer m.inflight.Dec()
		m.reqTotal.Inc()
		if r.URL.Query().Get("name") == "" {
			m.reqErrors.Inc()
			w.WriteHeader(http.StatusBadRequest)
			return
		}
		m.latencyHist.Observe(0.001)
		_, _ = w.Write([]byte(`ok`))
	})
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	srv := &http.Server{Handler: mux}
	go func() { _ = srv.Serve(ln) }()
	defer srv.Close()
	base := "http://" + ln.Addr().String()

	for i := 0; i < 2; i++ {
		if _, err := http.Get(base + "/api/hello?name=a"); err != nil {
			t.Fatalf("hello: %v", err)
		}
	}
	resp, _ := http.Get(base + "/api/hello")
	_ = resp.Body.Close()

	resp2, err := http.Get(base + "/metrics")
	if err != nil {
		t.Fatalf("metrics: %v", err)
	}
	defer resp2.Body.Close()
	if ct := resp2.Header.Get("Content-Type"); !strings.HasPrefix(ct, "text/plain; version=0.0.4") {
		t.Fatalf("Content-Type = %q", ct)
	}
	sc := bufio.NewScanner(resp2.Body)
	total, errors := -1, -1
	for sc.Scan() {
		line := sc.Text()
		if strings.HasPrefix(line, "http_requests_total") && !strings.HasPrefix(line, "http_requests_errors") {
			total, _ = strconv.Atoi(line[strings.LastIndex(line, " ")+1:])
		}
		if strings.HasPrefix(line, "http_requests_errors_total ") {
			errors, _ = strconv.Atoi(line[strings.LastIndex(line, " ")+1:])
		}
	}
	if total != 3 || errors != 1 {
		t.Fatalf("total=%d errors=%d, want 3/1", total, errors)
	}
}

// inflight 在请求进出时 +1/-1，最终归零
func TestInflightReturnsToZero(t *testing.T) {
	m := newAppMetrics()
	h := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		m.inflight.Inc()
		defer m.inflight.Dec()
		_, _ = w.Write([]byte("ok"))
	})
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest("GET", "/", nil))
	m.inflight.mu.Lock()
	defer m.inflight.mu.Unlock()
	if m.inflight.value != 0 {
		t.Fatalf("inflight = %v, want 0", m.inflight.value)
	}
}
