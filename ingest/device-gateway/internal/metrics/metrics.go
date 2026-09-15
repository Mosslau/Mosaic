// Package metrics 定义网关的 Prometheus 指标与 pprof 挂载。
package metrics

import (
	"net/http"
	"net/http/pprof"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// 指标命名约定: gateway_ 前缀, 单位做后缀(_seconds/_total)
var (
	// RequestsTotal HTTP 请求计数, 按路径与结果分类
	RequestsTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Namespace: "gateway",
		Name:      "requests_total",
		Help:      "HTTP 请求总数, result ∈ {ok, unauthorized, rate_limited, invalid_body, invalid_data, kafka_error}",
	}, []string{"path", "result"})

	// RequestDuration HTTP 处理耗时分布
	RequestDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Namespace: "gateway",
		Name:      "request_duration_seconds",
		Help:      "HTTP 请求处理耗时",
		Buckets:   []float64{0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1},
	}, []string{"path"})

	// KafkaWriteTotal Kafka 写入结果计数(async 回调中统计)
	KafkaWriteTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Namespace: "gateway",
		Name:      "kafka_write_total",
		Help:      "Kafka 写入总数, result ∈ {ok, error}",
	}, []string{"topic", "result"})

	// InflightRequests 当前在途请求数
	InflightRequests = promauto.NewGauge(prometheus.GaugeOpts{
		Namespace: "gateway",
		Name:      "inflight_requests",
		Help:      "当前正在处理的请求数",
	})
)

// Instrument 包裹一个 handler: 统计在途数与耗时。result 由 handler 内部通过 RequestsTotal 自行上报。
func Instrument(path string, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		InflightRequests.Inc()
		timer := prometheus.NewTimer(RequestDuration.WithLabelValues(path))
		defer func() {
			timer.ObserveDuration()
			InflightRequests.Dec()
		}()
		next.ServeHTTP(w, r)
	})
}

// RegisterHandlers 把 /metrics 与 /debug/pprof 挂到给定 mux 上
func RegisterHandlers(mux *http.ServeMux) {
	mux.Handle("/metrics", promhttp.Handler())
	mux.HandleFunc("/debug/pprof/", pprof.Index)
	mux.HandleFunc("/debug/pprof/cmdline", pprof.Cmdline)
	mux.HandleFunc("/debug/pprof/profile", pprof.Profile)
	mux.HandleFunc("/debug/pprof/symbol", pprof.Symbol)
	mux.HandleFunc("/debug/pprof/trace", pprof.Trace)
}
