package handler

import (
	"time"

	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/metrics"
)

// observeIngestLatency 记录上行链路延迟: EMQX 接收(信封 ts, 毫秒) → 当前时刻。
//
// 为什么用 EMQX 的时间戳, 而不是设备上报的 ts:
// 设备侧 `ts` 在契约上是 Unix **秒**(GB32960 的数据单元时间也是 6B 秒级),
// 量化误差就有 1s, 而链路真实延迟是百毫秒级 —— 误差比信号大一个量级, 测出来没有鉴别力。
// EMQX 信封里本来就带毫秒接收时间戳, 用它观测"平台内部这一段"(webhook 转发 + 治理 +
// 落盘确认)可以做到毫秒精度, 且**零契约改动**(《接入层设计》§9)。
//
// 语义注意: EMQX webhook 重试时该时间戳不变, 因此"网关连续 5xx → EMQX 退避重试"
// 会如实地表现为 ingest 延迟上涨 —— 这是想要的信号, 不是缺陷。
//
// 防御: 时间戳缺失(<=0, 例如规则未取 timestamp)或算出负值(时钟回拨/主机不同步)时
// 不观测 —— 噪声样本比缺样本更糟, 会污染分位数。
func observeIngestLatency(channel string, emqxTsMS int64) {
	if emqxTsMS <= 0 {
		return
	}
	d := time.Since(time.UnixMilli(emqxTsMS))
	if d < 0 {
		return
	}
	metrics.IngestLatency.WithLabelValues(channel).Observe(d.Seconds())
}
