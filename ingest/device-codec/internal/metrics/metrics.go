// Package metrics device-codec 的 Prometheus 指标与健康探针。
//
// 为什么 codec 需要自己的可观测(2026-09-18 补齐):
//   - 它是"数据不丢"链路上唯一会**丢弃**消息的环节(帧级/单元级 DLQ), 丢弃必须可计数、可告警
//   - 消费 lag 决定了实时性(网关侧有 inflight, codec 侧只有 lag 能反映积压)
//   - 第 2 阶段 K8s 化需要 /health 做 liveness/readiness, /metrics 做 HPA 与看板
package metrics

import (
	"encoding/json"
	"net/http"
	"net/http/pprof"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	dto "github.com/prometheus/client_model/go"
)

// 指标命名约定: codec_ 前缀(与网关 gateway_ 前缀区分), 单位做后缀
var (
	// ConsumedTotal 消费的原始帧数(每条 Kafka 消息 = 一帧)
	ConsumedTotal = promauto.NewCounter(prometheus.CounterOpts{
		Namespace: "codec",
		Name:      "consumed_total",
		Help:      "device-codec 消费的原始消息(帧)总数",
	})

	// DecodedTotal 解码产出的 L2 消息数, 按 type 分类
	// 与 ConsumedTotal 的比值反映"一帧平均拆出几条"(vehicle_status/battery_status/fault/charging/work)
	DecodedTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Namespace: "codec",
		Name:      "decoded_total",
		Help:      "解码产出的 VehicleReport 总数, type ∈ {vehicle_status, battery_status, fault, charging, work}",
	}, []string{"type"})

	// DLQTotal 进 DLQ 的消息数, 按阶段分类。
	// stage 取值与 cmd/server/main.go 的产出严格一致:
	// envelope=信封/base64/版本  parse=帧同步与BCC  decode=信息体解析  validate=契约校验  encode=产出序列化
	DLQTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Namespace: "codec",
		Name:      "dlq_total",
		Help:      "进入 DLQ 的消息总数, stage ∈ {envelope, parse, decode, validate, encode}",
	}, []string{"stage"})

	// FlushFailuresTotal 微批写出/位移提交失败次数。
	// 每次失败都会保留缓冲并退避重试(位移不提交 → 数据不丢); 该指标 >0 必须告警。
	FlushFailuresTotal = promauto.NewCounter(prometheus.CounterOpts{
		Namespace: "codec",
		Name:      "flush_failures_total",
		Help:      "微批写出或位移提交失败次数(失败批次保留待重试, 数据不丢)",
	})

	// PendingMessages 当前缓冲区中待写出的原始消息数。
	// 持续增长说明下游写不进去(该退避重试中), 是"丢数据之前"的最后一道可见信号。
	PendingMessages = promauto.NewGauge(prometheus.GaugeOpts{
		Namespace: "codec",
		Name:      "pending_messages",
		Help:      "缓冲区中待写出的原始消息数(持续增长=下游写不进去, 正在退避重试)",
	})

	// Lag 消费滞后(条) —— 实时性核心指标; 持续 >0 说明 codec 跟不上或下游写慢
	Lag = promauto.NewGauge(prometheus.GaugeOpts{
		Namespace: "codec",
		Name:      "consumer_lag",
		Help:      "消费者滞后条数(来自 kafka-go ReaderStats.Lag)",
	})

	// FlushDuration 微批"写出 + 提交位移"耗时分布
	FlushDuration = promauto.NewHistogram(prometheus.HistogramOpts{
		Namespace: "codec",
		Name:      "flush_duration_seconds",
		Help:      "微批写出+提交位移耗时",
		Buckets:   []float64{0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5},
	})

	// FlushBatchSize 每批处理的消息数(观察攒批是否生效: 期望接近 200, 稀疏时靠定时冲刷)
	FlushBatchSize = promauto.NewHistogram(prometheus.HistogramOpts{
		Namespace: "codec",
		Name:      "flush_batch_size",
		Help:      "每批处理的消息数",
		Buckets:   []float64{1, 5, 20, 50, 100, 200},
	})
)

// Handler 返回 /metrics + /health 的 mux。
// /health 语义: 进程存活即 up(不探测 Kafka —— codec 无状态, 依赖故障由 lag 指标与重启策略覆盖,
// 探针若探测外部依赖会在 Kafka 抖动时引发无意义的 Pod 重启)。
func Handler() http.Handler {
	mux := http.NewServeMux()
	mux.Handle("/metrics", promhttp.Handler())
	mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"status": "up",
			"lag":    currentLag(),
		})
	})
	return mux
}

// PprofHandler 返回 /debug/pprof/* 的 mux —— **只绑回环地址**。
// pprof 能读出进程内存(含凭据), 且 profile 可被反复调用消耗 CPU(2026-09-18 审计整改)。
func PprofHandler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/debug/pprof/", pprof.Index)
	mux.HandleFunc("/debug/pprof/cmdline", pprof.Cmdline)
	mux.HandleFunc("/debug/pprof/profile", pprof.Profile)
	mux.HandleFunc("/debug/pprof/symbol", pprof.Symbol)
	mux.HandleFunc("/debug/pprof/trace", pprof.Trace)
	return mux
}

// currentLag 读取当前 lag 值(供 /health 展示, 便于排障时一眼看到积压)。
// Gauge 无直接读值 API, 通过 Write 取快照。
func currentLag() float64 {
	m := &dto.Metric{}
	if err := Lag.Write(m); err != nil {
		return -1
	}
	return m.GetGauge().GetValue()
}
