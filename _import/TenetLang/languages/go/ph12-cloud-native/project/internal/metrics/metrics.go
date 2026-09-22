// Package metrics 手工 Prometheus 指标（text exposition 0.0.4，零第三方依赖）。
// 提供 counter/gauge/histogram 三种指标类型与注册表，/metrics 渲染与业务并发写安全。
// 设计：与 examples/ex04、exercises/sol-04 同构但作为独立库沉淀（project 复用）。
package metrics

import (
	"fmt"
	"sort"
	"strconv"
	"strings"
	"sync"
)

// Counter 只增不减（请求总数、错误总数）
type Counter struct {
	mu     sync.Mutex
	name   string
	help   string
	labels map[string]string
	value  float64
}

func NewCounter(name, help string, labels map[string]string) *Counter {
	return &Counter{name: name, help: help, labels: labels}
}

func (c *Counter) Inc() { c.Add(1) }

func (c *Counter) Add(v float64) {
	c.mu.Lock()
	c.value += v
	c.mu.Unlock()
}

func (c *Counter) Render(sb *strings.Builder) {
	c.mu.Lock()
	defer c.mu.Unlock()
	fmt.Fprintf(sb, "# HELP %s %s\n# TYPE %s counter\n", c.name, c.help, c.name)
	sb.WriteString(c.name)
	writeLabels(sb, c.labels)
	fmt.Fprintf(sb, " %s\n", formatFloat(c.value))
}

// Gauge 可增可减（在途请求数）
type Gauge struct {
	mu    sync.Mutex
	name  string
	help  string
	value float64
}

func NewGauge(name, help string) *Gauge { return &Gauge{name: name, help: help} }

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

func (g *Gauge) Render(sb *strings.Builder) {
	g.mu.Lock()
	defer g.mu.Unlock()
	fmt.Fprintf(sb, "# HELP %s %s\n# TYPE %s gauge\n", g.name, g.help, g.name)
	sb.WriteString(g.name)
	fmt.Fprintf(sb, " %s\n", formatFloat(g.value))
}

// Histogram 观测值分布（延迟/大小），带 _bucket/_sum/_count
type Histogram struct {
	mu      sync.Mutex
	name    string
	help    string
	buckets []float64
	counts  []uint64
	sum     float64
	count   uint64
}

func NewHistogram(name, help string, buckets []float64) *Histogram {
	return &Histogram{name: name, help: help, buckets: buckets, counts: make([]uint64, len(buckets))}
}

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

func (h *Histogram) Render(sb *strings.Builder) {
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

// Registry 指标注册表（按注册顺序渲染）
type Registry struct {
	mu     sync.Mutex
	groups []func(*strings.Builder)
}

func NewRegistry() *Registry { return &Registry{} }

func (r *Registry) Register(f func(*strings.Builder)) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.groups = append(r.groups, f)
}

// Render 输出完整 exposition 文本
func (r *Registry) Render() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	var sb strings.Builder
	for _, g := range r.groups {
		g(&sb)
	}
	return sb.String()
}

// writeLabels 输出 {k="v",...}，键排序保证输出稳定
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
