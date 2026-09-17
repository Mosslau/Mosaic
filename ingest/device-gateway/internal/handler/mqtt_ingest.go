package handler

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/Mosslau/OceanVerse/contracts/vehicle"
	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/metrics"
	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/model"
)

// MQTTIngestHandler 接收 EMQX 规则引擎 Webhook 推送的车端消息。
//
// 职责划分:
//   - EMQX: MQTT 协议终结、连接管理、QoS、会话(不管数据内容)
//   - 本端点: 治理——webhook 来源鉴权 → 契约校验 → Kafka 投递(与 HTTP 通道同一份契约)
//
// EMQX webhook 消息体(emqx.conf 中 body 模板定义):
//
//	{"clientid":"dev-OV00000001","topic":"ov/OV00000001/status",
//	 "qos":1,"ts":1758000000123,"payload":{...VehicleReport...}}
type MQTTIngestHandler struct {
	producer     Sender
	webhookToken string
}

func NewMQTTIngestHandler(p Sender, webhookToken string) *MQTTIngestHandler {
	return &MQTTIngestHandler{producer: p, webhookToken: webhookToken}
}

// emqxMessage EMQX webhook 信封
type emqxMessage struct {
	ClientID string          `json:"clientid"`
	Topic    string          `json:"topic"`
	QoS      int             `json:"qos"`
	Ts       int64           `json:"ts"`      // EMQX 时间戳(毫秒)
	Payload  json.RawMessage `json:"payload"` // 设备原始上报(vehicle.VehicleReport JSON)
}

// topic 后缀 → 数据类型(设备没填 type 时按 topic 推断)
var topicTypeMap = map[string]vehicle.ReportType{
	"status":  vehicle.ReportVehicleStatus,
	"battery": vehicle.ReportBatteryStatus,
	"fault":   vehicle.ReportFault,
}

// Ingest POST /api/v1/mqtt/ingest
func (h *MQTTIngestHandler) Ingest(w http.ResponseWriter, r *http.Request) {
	const path = "/api/v1/mqtt/ingest"

	if r.Method != http.MethodPost {
		model.WriteError(w, model.CodeMethodNotAllow, "仅支持 POST")
		return
	}

	// ① 来源鉴权: 只信任持有共享密钥的 EMQX
	if r.Header.Get("X-Webhook-Token") != h.webhookToken {
		metrics.RequestsTotal.WithLabelValues(path, "unauthorized").Inc()
		model.WriteError(w, model.CodeUnauthorized, "webhook 令牌非法")
		return
	}

	// ② 解析信封(单消息最大 64KB)
	r.Body = http.MaxBytesReader(w, r.Body, 64<<10)
	var msg emqxMessage
	if err := json.NewDecoder(r.Body).Decode(&msg); err != nil {
		metrics.RequestsTotal.WithLabelValues(path, "invalid_body").Inc()
		model.WriteError(w, model.CodeInvalidBody, "webhook 信封解析失败: "+err.Error())
		return
	}

	// ③ 解析设备载荷为平台契约
	var report vehicle.VehicleReport
	if err := json.Unmarshal(msg.Payload, &report); err != nil {
		metrics.RequestsTotal.WithLabelValues(path, "invalid_body").Inc()
		model.WriteError(w, model.CodeInvalidBody, "设备载荷解析失败: "+err.Error())
		return
	}

	// ④ 契约回填: VIN/type 缺失时按 MQTT 上下文推断(topic = ov/{vin}/{type})
	if parts := strings.Split(msg.Topic, "/"); len(parts) == 3 && parts[0] == "ov" {
		if report.VIN == "" {
			report.VIN = parts[1]
		}
		if report.Type == "" {
			report.Type = topicTypeMap[parts[2]]
		}
	}

	// ⑤ 与 HTTP 通道完全相同的校验(同一份契约, 同一套规则)
	if err := report.Validate(); err != nil {
		metrics.RequestsTotal.WithLabelValues(path, "invalid_data").Inc()
		model.WriteError(w, model.CodeInvalidData, err.Error())
		return
	}

	payload, err := report.Encode()
	if err != nil {
		metrics.RequestsTotal.WithLabelValues(path, "internal").Inc()
		model.WriteError(w, model.CodeInternal, "消息序列化失败")
		return
	}

	if err := h.producer.WriteReport(r.Context(), report.Key(), payload); err != nil {
		metrics.RequestsTotal.WithLabelValues(path, "kafka_error").Inc()
		// 返回 5xx 让 EMQX 重试(数据缓存在 EMQX 磁盘 buffer, 不丢)
		model.WriteError(w, model.CodeInternal, "消息投递失败")
		return
	}

	metrics.RequestsTotal.WithLabelValues(path, "ok").Inc()
	w.WriteHeader(http.StatusNoContent) // 204: 受理成功, 无响应体(webhook 惯例)
}
