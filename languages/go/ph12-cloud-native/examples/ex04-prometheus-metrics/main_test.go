package main

import (
	"bufio"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"sync"
	"testing"
)

// newTestServer 起真实 HTTP server（随机端口）并注册指标，返回 baseURL 与停止函数
func newTestServer(t *testing.T) (string, func()) {
	t.Helper()
	reg := newRegistry()
	m := newAppMetrics()
	m.registerAll(reg)

	mux := http.NewServeMux()
	mux.HandleFunc("GET /metrics", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
		_, _ = w.Write([]byte(reg.Render()))
	})
	mux.HandleFunc("GET /api/hello", func(w http.ResponseWriter, r *http.Request) {
		m.inflight.Inc()
		defer m.inflight.Dec()
		m.reqTotal.Inc()
		if r.URL.Query().Get("name") == "" {
			m.reqErrors.Inc()
			w.WriteHeader(http.StatusBadRequest)
			_, _ = w.Write([]byte(`{"error":"name required"}`))
			return
		}
		m.latencyHist.Observe(0.001)
		_, _ = w.Write([]byte(`{"hello":"x"}`))
	})

	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	srv := &http.Server{Handler: mux}
	go func() { _ = srv.Serve(ln) }()
	return "http://" + ln.Addr().String(), func() { _ = srv.Close() }
}

// TestExpositionFormat：counter/gauge/histogram 的文本必须符合 exposition 语法
func TestExpositionFormat(t *testing.T) {
	reg := newRegistry()
	m := newAppMetrics()
	m.registerAll(reg)

	m.reqTotal.Inc()
	m.reqTotal.Add(2) // 累计 3
	m.inflight.Inc()  // 1
	m.inflight.Dec()  // 0
	m.latencyHist.Observe(0.001)
	m.latencyHist.Observe(0.02)
	m.latencyHist.Observe(2.0) // 超过最大桶 1.0，只进 +Inf

	text := reg.Render()
	if !strings.Contains(text, "# HELP http_requests_total") {
		t.Fatal("缺 HELP 注释")
	}
	if !strings.Contains(text, "# TYPE http_requests_total counter") {
		t.Fatal("缺 counter TYPE 注释")
	}
	if !strings.Contains(text, `http_requests_total{handler="api"} 3`) {
		t.Fatalf("counter 值错误:\n%s", text)
	}
	if !strings.Contains(text, "http_requests_inflight 0") {
		t.Fatalf("gauge 值错误:\n%s", text)
	}
	// histogram：三个观测值按桶分布
	if !strings.Contains(text, `http_request_duration_seconds_bucket{le="0.005"} 1`) {
		t.Fatalf("bucket le=0.005 应为 1:\n%s", text)
	}
	if !strings.Contains(text, `http_request_duration_seconds_bucket{le="0.05"} 2`) {
		t.Fatalf("bucket le=0.05 应为 2:\n%s", text)
	}
	if !strings.Contains(text, `http_request_duration_seconds_bucket{le="+Inf"} 3`) {
		t.Fatalf("+Inf 桶应为 3:\n%s", text)
	}
	if !strings.Contains(text, "http_request_duration_seconds_sum 2.021") {
		t.Fatalf("sum 应为 2.021:\n%s", text)
	}
	if !strings.Contains(text, "http_request_duration_seconds_count 3") {
		t.Fatalf("count 应为 3:\n%s", text)
	}
}

// TestCounterNeverDecreases：counter 只增不减（Inc/Add 后值单调）
func TestCounterNeverDecreases(t *testing.T) {
	c := newCounter("x_total", "x help", nil)
	c.Add(5)
	c.Inc()
	if c.value != 6 {
		t.Fatalf("counter = %v, want 6", c.value)
	}
}

// TestLabelsSorted：多个标签按 key 排序输出（稳定可 diff）
func TestLabelsSorted(t *testing.T) {
	var sb strings.Builder
	writeLabels(&sb, map[string]string{"zone": "b", "method": "GET"})
	if sb.String() != `{method="GET",zone="b"}` {
		t.Fatalf("标签排序/格式错误: %s", sb.String())
	}
	// 空标签：不输出花括号
	sb.Reset()
	writeLabels(&sb, nil)
	if sb.String() != "" {
		t.Fatalf("空标签应无输出: %q", sb.String())
	}
}

// TestLabelEscaping：标签值里的引号/反斜杠要转义（防 exposition 注入）
func TestLabelEscaping(t *testing.T) {
	got := escapeLabel(`a"b\c`)
	if got != `a\"b\\c` {
		t.Fatalf("转义错误: %q", got)
	}
}

// TestFormatFloat：整数不带小数点（Prometheus 惯例），小数 %g 最短表示
func TestFormatFloat(t *testing.T) {
	if formatFloat(3) != "3" || formatFloat(2.5) != "2.5" || formatFloat(1e-3) != "0.001" {
		t.Fatalf("formatFloat 异常: %s %s %s", formatFloat(3), formatFloat(2.5), formatFloat(1e-3))
	}
}

// TestMetricsEndpoint：/metrics 可被 Prometheus 抓取（Content-Type + 200 + 可解析）
func TestMetricsEndpoint(t *testing.T) {
	base, stop := newTestServer(t)
	defer stop()

	resp, err := http.Get(base + "/metrics")
	if err != nil {
		t.Fatalf("GET /metrics: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want 200", resp.StatusCode)
	}
	if ct := resp.Header.Get("Content-Type"); !strings.HasPrefix(ct, "text/plain; version=0.0.4") {
		t.Fatalf("Content-Type = %q", ct)
	}
	body, _ := io.ReadAll(resp.Body)
	if !strings.Contains(string(body), "# TYPE http_requests_total counter") {
		t.Fatal("/metrics 缺 counter 指标")
	}
	// 抓取会更新 last_scrape 时间戳
	if !strings.Contains(string(body), "last_scrape_timestamp_seconds") {
		t.Fatal("/metrics 缺 last_scrape 指标")
	}
}

// TestScrapeIncrements：业务请求后 counter 增加，/metrics 反映最新值（拉模型的核心）
func TestScrapeIncrements(t *testing.T) {
	base, stop := newTestServer(t)
	defer stop()

	// 发 2 个成功 + 1 个失败请求
	for i := 0; i < 2; i++ {
		if _, err := http.Get(base + "/api/hello?name=a"); err != nil {
			t.Fatalf("GET hello: %v", err)
		}
	}
	resp, _ := http.Get(base + "/api/hello") // 缺 name → 400（计为错误）
	_ = resp.Body.Close()

	// 抓取并断言
	resp2, err := http.Get(base + "/metrics")
	if err != nil {
		t.Fatalf("GET /metrics: %v", err)
	}
	defer resp2.Body.Close()
	scanner := bufio.NewScanner(resp2.Body)
	foundTotal := false
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "http_requests_total") {
			val := line[strings.LastIndex(line, " ")+1:]
			n, err := strconv.Atoi(val)
			if err != nil || n != 3 {
				t.Fatalf("http_requests_total = %q, want 3", val)
			}
			foundTotal = true
		}
		if strings.HasPrefix(line, "http_requests_errors_total ") {
			val := line[strings.LastIndex(line, " ")+1:]
			if val != "1" {
				t.Fatalf("errors_total = %q, want 1", val)
			}
		}
	}
	if !foundTotal {
		t.Fatal("未找到 http_requests_total")
	}
}

// TestMethodSemantics：in-flight 计数在请求进出时 +1/-1（并发安全用 -race 验证）
func TestInflightTracking(t *testing.T) {
	reg := newRegistry()
	m := newAppMetrics()
	m.registerAll(reg)

	h := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		m.inflight.Inc()
		defer m.inflight.Dec()
		_, _ = w.Write([]byte("ok"))
	})
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest("GET", "/", nil))
	if m.inflight.value != 0 {
		t.Fatalf("inflight 应归零, got %v", m.inflight.value)
	}
}

// TestConcurrentScrapeAndTraffic：/metrics 渲染（读指标）与业务请求（写指标）并发——
// 模拟 Prometheus 每 10s 抓取期间持续有业务流量。指标值由各指标自带的互斥锁保护，
// 用 -race 验证零数据竞争（曾因指标无锁而失败，见场景 D 审计；此为防回归测试）。
func TestConcurrentScrapeAndTraffic(t *testing.T) {
	reg := newRegistry()
	m := newAppMetrics()
	m.registerAll(reg)

	mux := http.NewServeMux()
	mux.HandleFunc("GET /metrics", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
		_, _ = w.Write([]byte(reg.Render()))
	})
	mux.HandleFunc("GET /api/hello", func(w http.ResponseWriter, r *http.Request) {
		m.inflight.Inc()
		defer m.inflight.Dec()
		m.reqTotal.Inc()
		if r.URL.Query().Get("name") == "" {
			m.reqErrors.Inc()
		}
		m.latencyHist.Observe(0.001)
		_, _ = w.Write([]byte("ok"))
	})

	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	srv := &http.Server{Handler: mux}
	go func() { _ = srv.Serve(ln) }()
	defer srv.Close()
	base := "http://" + ln.Addr().String()

	var wg sync.WaitGroup
	for i := 0; i < 4; i++ {
		wg.Add(2)
		go func() {
			defer wg.Done()
			for j := 0; j < 200; j++ {
				resp, err := http.Get(base + "/api/hello?name=x")
				if err == nil {
					resp.Body.Close()
				}
			}
		}()
		go func() {
			defer wg.Done()
			for j := 0; j < 200; j++ {
				resp, err := http.Get(base + "/metrics")
				if err == nil {
					resp.Body.Close()
				}
			}
		}()
	}
	wg.Wait()
}
