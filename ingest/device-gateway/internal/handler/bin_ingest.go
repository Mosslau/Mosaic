package handler

import (
	"encoding/base64"
	"encoding/json"
	"net/http"
	"strings"

	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/metrics"
	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/model"
)

// BinIngestHandler 二进制透传通道(MQTT 载荷先行, §8-⑦)。
//
// 纪律: **不解帧**。帧同步/校验/解码全是 device-codec 的职责(§7 L1/L2 分层);
// 本端点只做三件事——验 webhook 密钥、从 topic 取 VIN、套信封进 ov.raw.binary.v1。
// proto_ver 恒为 "v1"(固有单元默认版本, §8-⑥); 自定义单元的版本字节在帧内, 由 codec 路由。
//
// EMQX webhook 消息体(emqx.conf 规则 SQL 用 base64_encode(payload) 产出):
//
//	{"clientid":"dev-OV00000001","topic":"ov/OV00000001/bin",
//	 "ts":1758000000123,"payload_b64":"IyMC/g..."}
type BinIngestHandler struct {
	producer     Sender
	webhookToken string
}

func NewBinIngestHandler(p Sender, webhookToken string) *BinIngestHandler {
	return &BinIngestHandler{producer: p, webhookToken: webhookToken}
}

// binEmqxMessage EMQX webhook 二进制信封(与 JSON 通道的 emqxMessage 分家: payload 是 base64)
type binEmqxMessage struct {
	ClientID   string `json:"clientid"`
	Topic      string `json:"topic"`
	Ts         int64  `json:"ts"`          // EMQX 时间戳(毫秒)
	PayloadB64 string `json:"payload_b64"` // 二进制帧(base64)
}

// rawEnvelope 写入 ov.raw.binary.v1 的信封(映射文档 §7)
type rawEnvelope struct {
	VIN      string `json:"vin"`
	Ts       int64  `json:"ts"`        // Unix 秒(取 EMQX 接收时间; 帧内数据时间由 codec 解析)
	ProtoVer string `json:"proto_ver"` // 线协议版本(固有单元默认 v1)
	Cmd      byte   `json:"cmd"`       // 帧命令字(仅窥 1 字节便于下游路由/统计, 不算解帧)
	Payload  string `json:"payload"`   // 原始帧 base64
}

// IngestBin POST /api/v1/bin/ingest
func (h *BinIngestHandler) IngestBin(w http.ResponseWriter, r *http.Request) {
	const path = "/api/v1/bin/ingest"

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

	// ② 解析信封(二进制帧 base64 后单消息放大 ~4/3, 上限 96KB)
	r.Body = http.MaxBytesReader(w, r.Body, 96<<10)
	var msg binEmqxMessage
	if err := json.NewDecoder(r.Body).Decode(&msg); err != nil {
		metrics.RequestsTotal.WithLabelValues(path, "invalid_body").Inc()
		model.WriteError(w, model.CodeInvalidBody, "webhook 信封解析失败: "+err.Error())
		return
	}

	// ③ 从 topic 取 VIN(topic = ov/{vin}/bin, ACL 语义同 JSON 通道)
	parts := strings.Split(msg.Topic, "/")
	if len(parts) != 3 || parts[0] != "ov" || parts[2] != "bin" || len(parts[1]) < 5 {
		metrics.RequestsTotal.WithLabelValues(path, "invalid_data").Inc()
		model.WriteError(w, model.CodeInvalidData, "topic 形态非法(期望 ov/{vin}/bin): "+msg.Topic)
		return
	}

	frame, err := base64.StdEncoding.DecodeString(msg.PayloadB64)
	if err != nil {
		metrics.RequestsTotal.WithLabelValues(path, "invalid_body").Inc()
		model.WriteError(w, model.CodeInvalidBody, "payload_b64 解码失败: "+err.Error())
		return
	}

	// ④ 套信封投递(Kafka key=VIN, 与 JSON 通道同一保序语义)
	env := rawEnvelope{VIN: parts[1], Ts: msg.Ts / 1000, ProtoVer: "v1", Payload: msg.PayloadB64}
	if len(frame) >= 3 {
		env.Cmd = frame[2] // 仅窥命令字; 帧同步/BCC/字段解析全在 codec
	}
	payload, err := json.Marshal(env)
	if err != nil {
		metrics.RequestsTotal.WithLabelValues(path, "internal").Inc()
		model.WriteError(w, model.CodeInternal, "信封序列化失败")
		return
	}
	if err := h.producer.WriteReport(r.Context(), []byte(env.VIN), payload); err != nil {
		metrics.RequestsTotal.WithLabelValues(path, "kafka_error").Inc()
		// 返回 5xx 让 EMQX 重试(与 JSON 通道同一兜底语义)
		model.WriteError(w, model.CodeInternal, "消息投递失败")
		return
	}

	metrics.RequestsTotal.WithLabelValues(path, "ok").Inc()
	w.WriteHeader(http.StatusNoContent) // 204: webhook 惯例
}
