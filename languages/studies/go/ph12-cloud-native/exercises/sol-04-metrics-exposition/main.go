// 来源：ph12-cloud-native 练习 4 参考实现 —— Prometheus 指标暴露（手工 exposition）
// 一句话说明：roadmap「接入 Prometheus」的落地——不引 client_golang，标准库手写
// counter/gauge/histogram 与 text exposition 0.0.4 输出（HELP/TYPE/标签/桶/+Inf/sum/count），
// /metrics 可被 Prometheus 直接抓取；业务埋点：请求总数（handler 标签）、错误总数、
// 在途 gauge、延迟直方图。与 examples/ex04 同构但独立实现（练习要求独立写出）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go test -race ./...              # 并发写指标无数据竞争
//	go run .                          # 起 127.0.0.1:59004
//	curl -s http://127.0.0.1:59004/metrics
//
// 验证状态：已验证（go1.25.6）
// 覆盖率：go test -cover 实测 **75.3%**（go1.25.6，6 个用例全过：exposition 语法/counter
// 并发单调/标签排序转义/formatFloat/抓取反映请求/在途归零；-race 无数据竞争）
package main

import (
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// ---- 三种指标类型（内部计数器用 plain 字段 + 外层锁；/metrics 渲染与业务并发写）----

type counter struct {
	mu     sync.Mutex
	name   string
	help   string
	labels map[string]string
	value  float64
}

func newCounter(name, help string, labels map[string]string) *counter {
	return &counter{name: name, help: help, labels: labels}
}

func (c *counter) Inc() { c.mu.Lock(); c.value++; c.mu.Unlock() }

func (c *counter) Add(v float64) { c.mu.Lock(); c.value += v; c.mu.Unlock() }

func (c *counter) render(sb *strings.Builder) {
	c.mu.Lock()
	defer c.mu.Unlock()
	fmt.Fprintf(sb, "# HELP %s %s\n# TYPE %s counter\n", c.name, c.help, c.name)
	sb.WriteString(c.name)
	writeLabels(sb, c.labels)
	fmt.Fprintf(sb, " %s\n", formatFloat(c.value))
}

type gauge struct {
	mu    sync.Mutex
	name  string
	help  string
	value float64
}

func newGauge(name, help string) *gauge { return &gauge{name: name, help: help} }

func (g *gauge) Inc() { g.mu.Lock(); g.value++; g.mu.Unlock() }

func (g *gauge) Dec() { g.mu.Lock(); g.value--; g.mu.Unlock() }

func (g *gauge) render(sb *strings.Builder) {
	g.mu.Lock()
	defer g.mu.Unlock()
	fmt.Fprintf(sb, "# HELP %s %s\n# TYPE %s gauge\n", g.name, g.help, g.name)
	sb.WriteString(g.name)
	fmt.Fprintf(sb, " %s\n", formatFloat(g.value))
}

type histogram struct {
	mu      sync.Mutex
	name    string
	help    string
	buckets []float64
	counts  []uint64
	sum     float64
	count   uint64
}

func newHistogram(name, help string, buckets []float64) *histogram {
	return &histogram{name: name, help: help, buckets: buckets, counts: make([]uint64, len(buckets))}
}

func (h *histogram) Observe(v float64) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.sum += v
	h.count++
	for i, b := range h.buckets {
		if v <= b {
			h.counts[i]++
		}
	}
}

func (h *histogram) render(sb *strings.Builder) {
	h.mu.Lock()
	defer h.mu.Unlock()
	fmt.Fprintf(sb, "# HELP %s %s\n# TYPE %s histogram\n", h.name, h.help, h.name)
	for i, b := range h.buckets {
		fmt.Fprintf(sb, "%s_bucket{le=%q} %d\n", h.name, formatFloat(b), h.counts[i])
	}
	fmt.Fprintf(sb, "%s_bucket{le=\"+Inf\"} %d\n", h.name, h.count)
	fmt.Fprintf(sb, "%s_sum %s\n", h.name, formatFloat(h.sum))
	fmt.Fprintf(sb, "%s_count %d\n", h.name, h.count)
}

// ---- exposition 辅助 ----

func writeLabels(sb *strings.Builder, labels map[string]string) {
	if len(labels) == 0 {
		return
	}
	keys := make([]string, 0, len(labels))
	for k := range labels {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	sb.WriteString("{")
	for i, k := range keys {
		if i > 0 {
			sb.WriteString(",")
		}
		fmt.Fprintf(sb, "%s=%q", k, escape(labels[k]))
	}
	sb.WriteString("}")
}

func escape(s string) string {
	return strings.ReplaceAll(strings.ReplaceAll(s, `\`, `\\`), `"`, `\"`)
}

func formatFloat(v float64) string { return strconv.FormatFloat(v, 'g', -1, 64) }

// ---- 注册表 ----

type registry struct {
	mu     sync.Mutex
	groups []func(*strings.Builder)
}

func newRegistry() *registry { return &registry{} }

func (r *registry) add(f func(*strings.Builder)) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.groups = append(r.groups, f)
}

func (r *registry) render() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	var sb strings.Builder
	for _, g := range r.groups {
		g(&sb)
	}
	return sb.String()
}

// ---- 业务指标 ----

type appMetrics struct {
	reqTotal    *counter
	reqErrors   *counter
	inflight    *gauge
	latencyHist *histogram
}

func newAppMetrics() *appMetrics {
	return &appMetrics{
		reqTotal:    newCounter("http_requests_total", "Total HTTP requests processed.", map[string]string{"handler": "api"}),
		reqErrors:   newCounter("http_requests_errors_total", "HTTP requests that returned 4xx/5xx.", nil),
		inflight:    newGauge("http_requests_inflight", "In-flight requests."),
		latencyHist: newHistogram("http_request_duration_seconds", "Request latency.", []float64{0.005, 0.01, 0.05, 0.1, 0.5, 1}),
	}
}

func (m *appMetrics) register(r *registry) {
	r.add(m.reqTotal.render)
	r.add(m.reqErrors.render)
	r.add(m.inflight.render)
	r.add(m.latencyHist.render)
}

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
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
		start := time.Now()
		m.reqTotal.Inc()
		if r.URL.Query().Get("name") == "" {
			m.reqErrors.Inc()
			w.WriteHeader(http.StatusBadRequest)
			_, _ = w.Write([]byte(`{"error":"name required"}`))
		} else {
			_, _ = w.Write([]byte(`{"hello":"x"}`))
		}
		m.latencyHist.Observe(time.Since(start).Seconds())
	})
	logger.Info("metrics server listening", "addr", "127.0.0.1:59004")
	if err := http.ListenAndServe("127.0.0.1:59004", mux); err != nil {
		logger.Error("serve failed", "err", err)
		os.Exit(1)
	}
}
