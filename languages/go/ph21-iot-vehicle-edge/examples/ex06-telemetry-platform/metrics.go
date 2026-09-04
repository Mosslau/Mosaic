// 来源：ph21-iot-vehicle-edge examples/ex06-telemetry-platform/metrics.go
// 一句话说明：Prometheus 文本指标（零第三方）——吞吐(ingested/cleaned)、错误率
// (clean_err 分 reason 标签)、在线车辆、告警计数。官方 client_golang 只是把同样的
// 文本格式做成库；此处手写足以离线教学与测试（主文档 3.9）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"fmt"
	"net/http"
	"sync/atomic"
)

// Metrics 最小指标集合。
type Metrics struct {
	ingested atomic.Int64 // 接入层收到
	cleaned  atomic.Int64 // 清洗通过入库
	cleanErr atomic.Int64 // 清洗失败（坏数据）
	alerts   atomic.Int64 // 告警命中
	online   atomic.Int64 // 在线设备数（gauge，由接入层心跳维护）
}

// Counters 快照（测试断言）。
func (m *Metrics) Counters() (ingested, cleaned, errs, alerts int64) {
	return m.ingested.Load(), m.cleaned.Load(), m.cleanErr.Load(), m.alerts.Load()
}

// SetOnline 由连接管理维护在线数。
func (m *Metrics) SetOnline(n int64) { m.online.Store(n) }

// ServeHTTP 输出 Prometheus text/plain 格式。命名遵循 <ns>_<name>{label="v"} value。
func (m *Metrics) ServeHTTP(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	fmt.Fprintf(w, "# HELP fleet_ingested_total 接入层收到的原始事件总数\n")
	fmt.Fprintf(w, "# TYPE fleet_ingested_total counter\n")
	fmt.Fprintf(w, "fleet_ingested_total %d\n", m.ingested.Load())
	fmt.Fprintf(w, "# HELP fleet_cleaned_total 清洗通过并落库的事件总数\n")
	fmt.Fprintf(w, "# TYPE fleet_cleaned_total counter\n")
	fmt.Fprintf(w, "fleet_cleaned_total %d\n", m.cleaned.Load())
	fmt.Fprintf(w, "# HELP fleet_clean_errors_total 清洗失败事件总数（按原因分标签）\n")
	fmt.Fprintf(w, "# TYPE fleet_clean_errors_total counter\n")
	fmt.Fprintf(w, "fleet_clean_errors_total{reason=%q} %d\n", "any", m.cleanErr.Load())
	fmt.Fprintf(w, "# HELP fleet_alerts_total 命中告警总数\n")
	fmt.Fprintf(w, "# TYPE fleet_alerts_total counter\n")
	fmt.Fprintf(w, "fleet_alerts_total %d\n", m.alerts.Load())
	fmt.Fprintf(w, "# HELP fleet_online_vehicles 当前在线车辆数\n")
	fmt.Fprintf(w, "# TYPE fleet_online_vehicles gauge\n")
	fmt.Fprintf(w, "fleet_online_vehicles %d\n", m.online.Load())
}
