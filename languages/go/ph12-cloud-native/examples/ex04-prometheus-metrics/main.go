// 来源：ph12-cloud-native 示例 4 —— 手工实现 Prometheus /metrics（exposition 格式）
// 一句话说明：不引入 prometheus/client_golang，用标准库手写三种指标类型并输出
// Prometheus text exposition 格式（0.0.4）：counter（只增不减）、gauge（可增可减）、
// histogram（分桶计数 + sum + count），带 HELP/TYPE 注释与标签（labels）。
// 核心收获：看懂 /metrics 文本 = 看懂一切 Go 服务暴露的指标，也就能自己接 Prometheus
// 抓取（scrape）与 Grafana 展示。全部标准库，可离线实测。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go run .                                    # 起 127.0.0.1:58004
//	curl -s http://127.0.0.1:58004/metrics      # 看 exposition 文本
//	curl -s http://127.0.0.1:58004/api/hello    # 触发一次请求（count+1、记录 latency）
//
// 验证状态：已验证（go1.25.6）
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

// ---- 指标注册表：metric 名 -> 样本，全部用 sync.Mutex 保护（/metrics 与业务并发写）----

// Counter 只增不减的计数：请求总数、错误总数。重置只能靠进程重启。
// mu 保护 value：/metrics 渲染（读）与业务 handler（写）并发，读写都加锁（练习 4 的要求）。
type Counter struct {
	mu     sync.Mutex
	name   string
	help   string
	labels map[string]string
	value  float64
}

func newCounter(name, help string, labels map[string]string) *Counter {
	return &Counter{name: name, help: help, labels: labels}
}

func (c *Counter) Inc() { c.Add(1) }

func (c *Counter) Add(v float64) {
	c.mu.Lock()
	c.value += v
	c.mu.Unlock()
}

// render 输出一行样本（标签按 key 排序，保证输出稳定、可 diff）
func (c *Counter) render(sb *strings.Builder) {
	c.mu.Lock()
	defer c.mu.Unlock()
	fmt.Fprintf(sb, "# HELP %s %s\n", c.name, c.help)
	fmt.Fprintf(sb, "# TYPE %s counter\n", c.name)
	sb.WriteString(c.name)
	writeLabels(sb, c.labels)
	fmt.Fprintf(sb, " %s\n", formatFloat(c.value))
}

// Gauge 可增可减的当前值：在途请求数、队列长度、最后处理时间戳。
type Gauge struct {
	mu     sync.Mutex
	name   string
	help   string
	labels map[string]string
	value  float64
}

func newGauge(name, help string, labels map[string]string) *Gauge {
	return &Gauge{name: name, help: help, labels: labels}
}

func (g *Gauge) Inc() {
	g.mu.Lock()
	g.value++
	g.mu.Unlock()
}

func (g *Gauge) Dec() {
	g.mu.Lock()
	g.value--
	g.mu.Unlock()
}

func (g *Gauge) Set(v float64) {
	g.mu.Lock()
	g.value = v
	g.mu.Unlock()
}

func (g *Gauge) render(sb *strings.Builder) {
	g.mu.Lock()
	defer g.mu.Unlock()
	fmt.Fprintf(sb, "# HELP %s %s\n", g.name, g.help)
	fmt.Fprintf(sb, "# TYPE %s gauge\n", g.name)
	sb.WriteString(g.name)
	writeLabels(sb, g.labels)
	fmt.Fprintf(sb, " %s\n", formatFloat(g.value))
}

// Histogram 观测值分布：按桶（bucket）计数，_bucket{le="..."} 为"小于等于该上界的样本数"，
// 另加 _sum（总和）与 _count（样本数）。用于延迟/大小分布，PromQL 里可算分位数。
type Histogram struct {
	mu      sync.Mutex
	name    string
	help    string
	buckets []float64 // 桶上界（升序）
	counts  []uint64  // 每个桶的累计计数（le<=上界）
	sum     float64
	count   uint64
}

func newHistogram(name, help string, buckets []float64) *Histogram {
	return &Histogram{name: name, help: help, buckets: buckets, counts: make([]uint64, len(buckets))}
}

// Observe 记录一个观测值：找到第一个 >= v 的桶，给该桶及其后所有累计桶 +1
func (h *Histogram) Observe(v float64) {
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

func (h *Histogram) render(sb *strings.Builder) {
	h.mu.Lock()
	defer h.mu.Unlock()
	fmt.Fprintf(sb, "# HELP %s %s\n", h.name, h.help)
	fmt.Fprintf(sb, "# TYPE %s histogram\n", h.name)
	for i, b := range h.buckets {
		fmt.Fprintf(sb, "%s_bucket{le=%q} %d\n", h.name, formatFloat(b), h.counts[i])
	}
	fmt.Fprintf(sb, "%s_bucket{le=\"+Inf\"} %d\n", h.name, h.count)
	fmt.Fprintf(sb, "%s_sum %s\n", h.name, formatFloat(h.sum))
	fmt.Fprintf(sb, "%s_count %d\n", h.name, h.count)
}

// writeLabels 写 {k="v",k2="v2"}（无标签则省略花括号）；标签名/值按 Prometheus 约定做转义
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
		fmt.Fprintf(sb, "%s=%q", k, escapeLabel(labels[k]))
	}
	sb.WriteString("}")
}

// escapeLabel 转义标签值中的引号与反斜杠（Prometheus exposition 转义规则）
func escapeLabel(s string) string {
	return strings.ReplaceAll(strings.ReplaceAll(s, `\`, `\\`), `"`, `\"`)
}

// formatFloat 用 %g 输出浮点（Prometheus 风格：整数不带小数点）
func formatFloat(v float64) string {
	return strconv.FormatFloat(v, 'g', -1, 64)
}

// ---- 应用层：注册表 + 观测对象 ----

type registry struct {
	mu     sync.Mutex
	groups []func(*strings.Builder) // 各指标的 render 集合
}

func newRegistry() *registry { return &registry{} }

// register 注册一个 render 函数（counter/gauge/histogram 各自提供）
func (r *registry) register(f func(*strings.Builder)) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.groups = append(r.groups, f)
}

// Render 按注册顺序输出全部指标文本（Prometheus 要求指标名全局唯一，注册时自行保证）
func (r *registry) Render() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	var sb strings.Builder
	for _, g := range r.groups {
		g(&sb)
	}
	return sb.String()
}

// ---- 业务指标实例 ----

type appMetrics struct {
	reqTotal     *Counter   // 总请求数（按 handler 分标签）
	reqErrors    *Counter   // 错误请求数
	inflight     *Gauge     // 在途请求数
	latencyHist  *Histogram // 请求延迟直方图（秒）
	lastScrapeAt *Gauge     // 上次抓取时间戳（Unix 秒）
}

func newAppMetrics() *appMetrics {
	m := &appMetrics{
		reqTotal:     newCounter("http_requests_total", "Total HTTP requests processed.", map[string]string{"handler": "api"}),
		reqErrors:    newCounter("http_requests_errors_total", "Total HTTP requests that returned 5xx.", nil),
		inflight:     newGauge("http_requests_inflight", "Current number of in-flight requests.", nil),
		latencyHist:  newHistogram("http_request_duration_seconds", "Request latency distribution.", []float64{0.005, 0.01, 0.05, 0.1, 0.5, 1}),
		lastScrapeAt: newGauge("last_scrape_timestamp_seconds", "Unix timestamp of the last scrape.", nil),
	}
	return m
}

func (m *appMetrics) registerAll(r *registry) {
	r.register(m.reqTotal.render)
	r.register(m.reqErrors.render)
	r.register(m.inflight.render)
	r.register(m.latencyHist.render)
	r.register(m.lastScrapeAt.render)
}

// ---- HTTP 服务 ----

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	reg := newRegistry()
	metrics := newAppMetrics()
	metrics.registerAll(reg)

	mux := http.NewServeMux()

	// /metrics：Prometheus 默认抓取路径（拉模型：Prometheus 定时来 GET）
	mux.HandleFunc("GET /metrics", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
		metrics.lastScrapeAt.Set(float64(time.Now().Unix()))
		_, _ = w.Write([]byte(reg.Render()))
	})

	// 业务接口：记录请求数、在途数、延迟
	mux.HandleFunc("GET /api/hello", func(w http.ResponseWriter, r *http.Request) {
		metrics.inflight.Inc()
		defer metrics.inflight.Dec()
		start := time.Now()
		metrics.reqTotal.Inc()

		name := r.URL.Query().Get("name")
		if name == "" {
			metrics.reqErrors.Inc() // 错误也要计数（PromQL: rate(errors) / rate(total) = 错误率）
			w.WriteHeader(http.StatusBadRequest)
			_, _ = w.Write([]byte(`{"error":"name required"}`))
		} else {
			_, _ = w.Write([]byte(fmt.Sprintf(`{"hello":"%s"}`, name)))
		}
		metrics.latencyHist.Observe(time.Since(start).Seconds())
	})

	logger.Info("metrics server listening", "addr", "127.0.0.1:58004")
	if err := http.ListenAndServe("127.0.0.1:58004", mux); err != nil {
		logger.Error("serve failed", "err", err)
		os.Exit(1)
	}
}
