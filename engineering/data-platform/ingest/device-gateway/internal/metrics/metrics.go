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
		Help:      "HTTP 请求总数, result ∈ {ok, unauthorized, rate_limited, invalid_body, invalid_data, kafka_error, internal, vin_mismatch}",
	}, []string{"path", "result"})

	// RequestDuration HTTP 处理耗时分布
	RequestDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Namespace: "gateway",
		Name:      "request_duration_seconds",
		Help:      "HTTP 请求处理耗时",
		Buckets:   []float64{0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1},
	}, []string{"path"})

	// KafkaWriteTotal Kafka 写入结果计数(同步投递: 写入返回后统计)
	KafkaWriteTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Namespace: "gateway",
		Name:      "kafka_write_total",
		Help:      "Kafka 写入总数, result ∈ {ok, error, canceled}(canceled=调用方主动取消, 非 broker 故障)",
	}, []string{"topic", "result"})

	// InflightRequests 当前在途请求数
	InflightRequests = promauto.NewGauge(prometheus.GaugeOpts{
		Namespace: "gateway",
		Name:      "inflight_requests",
		Help:      "当前正在处理的请求数",
	})

	// IngestLatency 上行链路延迟: EMQX 接收消息 → 网关受理完成(含 broker 落盘确认)。
	// 用 EMQX 信封里的**毫秒**时间戳计算, 因此这一段是精确的 —— 不受设备侧
	// 秒级 ts 的量化误差影响(§9 的"分段延迟之间没有桥", 2026-09-18 补)。
	IngestLatency = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Namespace: "gateway",
		Name:      "ingest_latency_seconds",
		Help:      "EMQX 接收到消息 → 网关受理完成(broker 确认)的耗时, channel ∈ {mqtt, bin}",
		Buckets:   []float64{0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5},
	}, []string{"channel"})
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

// RegisterMetrics 把 /metrics 挂到给定 mux。
// 指标端点需要被 Prometheus(容器内)抓取, 因此监听在专用端口(默认 18081)而非业务端口。
func RegisterMetrics(mux *http.ServeMux) {
	mux.Handle("/metrics", promhttp.Handler())
}

// RegisterPprof 把 /debug/pprof 挂到给定 mux。
// pprof 能读出进程内存(含 webhook 密钥/设备 token), 且 profile 可被反复调用消耗 CPU,
// 因此**只绑回环地址**(2026-09-18 审计整改: 此前与业务端口共用并监听全网卡)。
func RegisterPprof(mux *http.ServeMux) {
	mux.HandleFunc("/debug/pprof/", pprof.Index)
	mux.HandleFunc("/debug/pprof/cmdline", pprof.Cmdline)
	mux.HandleFunc("/debug/pprof/profile", pprof.Profile)
	mux.HandleFunc("/debug/pprof/symbol", pprof.Symbol)
	mux.HandleFunc("/debug/pprof/trace", pprof.Trace)
}
