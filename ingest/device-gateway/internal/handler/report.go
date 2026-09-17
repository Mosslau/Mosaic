// Package handler HTTP 处理层: 解析 → 校验 → 投递 Kafka → 202。
// 原则: handler 不做任何业务判断(那属于 Flink/告警服务), 只保证数据干净地进入总线。
package handler

import (
	"context"
	"encoding/json"
	"net/http"

	"github.com/Mosslau/OceanVerse/ingest/device-contracts/vehicle"
	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/metrics"
	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/model"
)

// Sender 消息投递接口(kafka.Producer 实现)。依赖接口便于测试与替换。
type Sender interface {
	WriteReport(ctx context.Context, key, payload []byte) error
}

// ReportHandler 处理车端上报
type ReportHandler struct {
	producer Sender
}

func NewReportHandler(p Sender) *ReportHandler {
	return &ReportHandler{producer: p}
}

// Report POST /api/v1/vehicle/report
// 成功返回 202 Accepted: 数据已受理并异步投递, 调用方无需等待 Kafka 落盘。
func (h *ReportHandler) Report(w http.ResponseWriter, r *http.Request) {
	path := r.URL.Path
	if r.Method != http.MethodPost {
		model.WriteError(w, model.CodeMethodNotAllow, "仅支持 POST")
		return
	}

	// ① 限制请求体最大 64KB, 防畸形大报文打爆内存
	r.Body = http.MaxBytesReader(w, r.Body, 64<<10)
	var report vehicle.VehicleReport
	if err := json.NewDecoder(r.Body).Decode(&report); err != nil {
		metrics.RequestsTotal.WithLabelValues(path, "invalid_body").Inc()
		model.WriteError(w, model.CodeInvalidBody, "JSON 解析失败: "+err.Error())
		return
	}

	// ② 契约校验(网关第一道防线, 拒绝时告知具体原因便于设备端排查)
	if err := report.Validate(); err != nil {
		metrics.RequestsTotal.WithLabelValues(path, "invalid_data").Inc()
		model.WriteError(w, model.CodeInvalidData, err.Error())
		return
	}

	// ③ 序列化为 Kafka 消息体(契约 JSON)
	payload, err := report.Encode()
	if err != nil {
		metrics.RequestsTotal.WithLabelValues(path, "internal").Inc()
		model.WriteError(w, model.CodeInternal, "消息序列化失败")
		return
	}

	// ④ 投递 Kafka(key=VIN 保序)。失败返回 500 让设备重试——
	// 此时消息可能仍在客户端缓冲, 设备重试 + Kafka 重试可能造成重复,
	// 下游按 (vin, ts) 幂等去重(契约设计已预留)。
	if err := h.producer.WriteReport(r.Context(), report.Key(), payload); err != nil {
		metrics.RequestsTotal.WithLabelValues(path, "kafka_error").Inc()
		model.WriteError(w, model.CodeInternal, "消息投递失败")
		return
	}

	metrics.RequestsTotal.WithLabelValues(path, "ok").Inc()
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(http.StatusAccepted)
	_ = json.NewEncoder(w).Encode(map[string]any{"code": 0, "message": "accepted"})
}

// Health GET /health 健康探针(K8s liveness/readiness 用)
func Health(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "up"})
}
