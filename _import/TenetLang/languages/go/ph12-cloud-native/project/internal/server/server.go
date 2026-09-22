// Package server 可部署 API 服务模板的 HTTP 层：
// /healthz（liveness）+ /readyz（readiness）+ /metrics（Prometheus 抓取）+ 业务接口，
// 就绪状态 atomic.Bool 控制、请求级 slog 日志、指标埋点。
// 探针语义与优雅退出编排在 cmd/api/main.go（收到信号 → 摘 readiness → Shutdown）。
package server

import (
	"log/slog"
	"net/http"
	"sync/atomic"
	"time"

	"tenetlang/go/ph12-cloud-native/project/internal/metrics"
)

// Server HTTP 服务：持有就绪状态与指标
type Server struct {
	ready   atomic.Bool
	metrics *Metrics
	logger  *slog.Logger
}

// Metrics 项目级指标集合（可独立注册，便于测试）
type Metrics struct {
	Registry    *metrics.Registry
	ReqTotal    *metrics.Counter
	ReqErrors   *metrics.Counter
	Inflight    *metrics.Gauge
	LatencyHist *metrics.Histogram
}

// NewMetrics 创建并注册全部指标
func NewMetrics() *Metrics {
	reg := metrics.NewRegistry()
	m := &Metrics{
		Registry:    reg,
		ReqTotal:    metrics.NewCounter("http_requests_total", "Total HTTP requests processed.", map[string]string{"handler": "api"}),
		ReqErrors:   metrics.NewCounter("http_requests_errors_total", "HTTP requests that returned 4xx/5xx.", nil),
		Inflight:    metrics.NewGauge("http_requests_inflight", "In-flight requests."),
		LatencyHist: metrics.NewHistogram("http_request_duration_seconds", "Request latency.", []float64{0.005, 0.01, 0.05, 0.1, 0.5, 1}),
	}
	reg.Register(m.ReqTotal.Render)
	reg.Register(m.ReqErrors.Render)
	reg.Register(m.Inflight.Render)
	reg.Register(m.LatencyHist.Render)
	return m
}

// New 创建服务（未就绪；应用在依赖就绪后调 MarkReady）
func New(logger *slog.Logger, m *Metrics) *Server {
	s := &Server{metrics: m, logger: logger}
	s.ready.Store(false)
	return s
}

// MarkReady 依赖就绪后调用（/readyz 变 200）
func (s *Server) MarkReady() { s.ready.Store(true) }

// Ready 当前就绪状态（优雅退出时置 false）
func (s *Server) SetReady(v bool) { s.ready.Store(v) }

// Handler 装配全部路由
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.handleHealthz)
	mux.HandleFunc("GET /readyz", s.handleReadyz)
	mux.HandleFunc("GET /metrics", s.handleMetrics)
	mux.HandleFunc("GET /api/devices/{id}", s.handleGetDevice)
	return mux
}

// handleHealthz liveness：进程活着即 200（不查依赖）
func (s *Server) handleHealthz(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"ok"}`))
}

// handleReadyz readiness：未就绪 503（流量摘除），就绪 200
func (s *Server) handleReadyz(w http.ResponseWriter, _ *http.Request) {
	status, body := http.StatusOK, `{"status":"ready"}`
	if !s.ready.Load() {
		status, body = http.StatusServiceUnavailable, `{"status":"not_ready"}`
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write([]byte(body))
}

// handleMetrics Prometheus 抓取端点
func (s *Server) handleMetrics(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
	_, _ = w.Write([]byte(s.metrics.Registry.Render()))
}

// handleGetDevice 业务接口示例（ph10 数据层接入点）：记录指标 + 请求级日志
func (s *Server) handleGetDevice(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	s.metrics.Inflight.Inc()
	defer s.metrics.Inflight.Dec()
	s.metrics.ReqTotal.Inc()

	id := r.PathValue("id")
	s.logger.InfoContext(r.Context(), "get device",
		"device_id", id, "method", r.Method, "path", r.URL.Path)

	if !s.ready.Load() {
		s.metrics.ReqErrors.Inc()
		w.WriteHeader(http.StatusServiceUnavailable)
		_, _ = w.Write([]byte(`{"error":"not ready"}`))
		return
	}
	if id == "" {
		s.metrics.ReqErrors.Inc()
		w.WriteHeader(http.StatusBadRequest)
		_, _ = w.Write([]byte(`{"error":"device id required"}`))
		return
	}
	// 业务返回（真实数据源接入见 ph10 数据库阶段；此处模板化）
	w.Header().Set("Content-Type", "application/json")
	_, _ = w.Write([]byte(`{"device_id":"` + id + `","status":"online"}`))
	s.metrics.LatencyHist.Observe(time.Since(start).Seconds())
}
