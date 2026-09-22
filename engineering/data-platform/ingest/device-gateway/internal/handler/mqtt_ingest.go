package handler

import (
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/Mosslau/OceanVerse/ingest/device-contracts/vehicle"
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

	// ① 来源鉴权: 只信任持有共享密钥的 EMQX(常量时间比较)
	if !checkWebhookToken(w, r, h.webhookToken, path) {
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

	// ④ 契约回填 + 身份锚点: topic 契约 = ov/{vin}/{type}(《接入层设计》§4.2 唯一源)。
	// 这里用与二进制通道**同一个** topicVIN（webhook_auth.go）——
	// 修复前本处自写了一套 Split, 对 VIN 长度无约束, 与 bin_ingest 的 >=5 不一致;
	// 更糟的是 topic 形态意外时 topicV 为空会**静默跳过**下面的 VIN 一致性校验。
	// 现在: 形态/长度/后缀任一不合法 → 400, 绝不进入"没有身份锚点"的分支。
	vinFromTopic, suffix, ok := splitTopic(msg.Topic)
	if !ok {
		metrics.RequestsTotal.WithLabelValues(path, "invalid_data").Inc()
		model.WriteError(w, model.CodeInvalidData,
			"topic 形态非法(期望 ov/{vin}/{status|battery|fault}): "+msg.Topic)
		return
	}
	reportType, knownSuffix := topicTypeMap[suffix]
	if !knownSuffix {
		metrics.RequestsTotal.WithLabelValues(path, "invalid_data").Inc()
		model.WriteError(w, model.CodeInvalidData, "未知 topic 后缀(期望 status|battery|fault): "+suffix)
		return
	}
	topicV, ok := topicVIN(msg.Topic, suffix, topicVINMinLen(suffix))
	if !ok {
		metrics.RequestsTotal.WithLabelValues(path, "invalid_data").Inc()
		model.WriteError(w, model.CodeInvalidData,
			fmt.Sprintf("topic 中的 vin 非法(长度必须 >=%d): %s", topicVINMinLen(suffix), vinFromTopic))
		return
	}
	if report.VIN == "" {
		report.VIN = topicV
	}
	if report.Type == "" {
		report.Type = reportType
	}

	// ④.5 VIN 一致性(ACL 之后的第二道身份锚点):
	// EMQX ACL 只约束"能发哪个 topic", 不约束 payload 内容。若允许载荷 VIN 覆盖 topic VIN,
	// 任何持有合法凭证的设备都能以他人 VIN 写入数据(污染他人车辆画像/告警)。
	// 载荷显式携带 VIN 时必须与 topic 一致; 不一致直接拒绝。
	if report.VIN != topicV {
		metrics.RequestsTotal.WithLabelValues(path, "vin_mismatch").Inc()
		model.WriteError(w, model.CodeInvalidData,
			"载荷 vin 与 topic 不一致(topic="+topicV+", payload="+report.VIN+")")
		return
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
	observeIngestLatency("mqtt", msg.Ts) // 上行延迟 SLI: EMQX 接收 → 本例受理完成
	w.WriteHeader(http.StatusNoContent)  // 204: 受理成功, 无响应体(webhook 惯例)
}
