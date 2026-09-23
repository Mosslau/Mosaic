package handler

import (
	"crypto/subtle"
	"net/http"
	"strings"

	"github.com/Mosslau/Mosaic/ingest/device-contracts/vehicle"
	"github.com/Mosslau/Mosaic/ingest/device-gateway/internal/metrics"
	"github.com/Mosslau/Mosaic/ingest/device-gateway/internal/model"
)

// webhookTokenHeader EMQX webhook 来源鉴权头
const webhookTokenHeader = "X-Webhook-Token"

// checkWebhookToken 校验来源是否为持有共享密钥的 EMQX。
// 用 crypto/subtle 常量时间比较: 普通 == 会在首个不同字节处提前返回,
// 泄漏"前缀猜对了几位"的时序信息(webhook 密钥是唯一凭据, 值得用常量时间比较)。
// 鉴权失败计入 unauthorized 指标, 便于对暴力尝试告警。
func checkWebhookToken(w http.ResponseWriter, r *http.Request, want, path string) bool {
	got := r.Header.Get(webhookTokenHeader)
	// 长度不同直接拒绝(长度本身不是秘密); 等长时用常量时间比较
	if len(got) != len(want) || subtle.ConstantTimeCompare([]byte(got), []byte(want)) != 1 {
		metrics.RequestsTotal.WithLabelValues(path, "unauthorized").Inc()
		model.WriteError(w, model.CodeUnauthorized, "webhook 令牌非法")
		return false
	}
	return true
}

// topicVIN 从 MQTT topic 提取 VIN 并校验形态: ov/{vin}/{suffix}。
// 返回 ok=false 表示 topic 形态非法, 调用方应回 400。
//
// 这是网关侧**唯一**的 topic 解析实现(2026-09-20 收敛):
// 修复前 JSON 通道(mqtt_ingest.go 的 ④)与二进制通道(bin_ingest.go 的 ③)各写了一套 ——
// 前者用 strings.Split 后自行判 3 段, 对 VIN 长度**无约束**, 后者要求 >=5 字符,
// 于是同一份 topic 契约在两条通道上判据不同(超短 VIN 在 JSON 通道能过, 在二进制通道被拒)。
// 现在两条通道统一走本函数, 长度约束由调用方按通道给出(见各 handler 的 topicVINMinLen)。
func topicVIN(topic, suffix string, minVINLen int) (string, bool) {
	vin, sfx, ok := splitTopic(topic)
	if !ok || sfx != suffix || len(vin) < minVINLen {
		return "", false
	}
	return vin, true
}

// splitTopic 解析 ov/{vin}/{suffix} 三段形态, 不做任何语义约束(调用方决定)。
// 单独抽出是为了让"形态非法"与"语义非法(长度/后缀)"可以给不同的错误信息。
func splitTopic(topic string) (vin, suffix string, ok bool) {
	parts := strings.Split(topic, "/")
	if len(parts) != 3 || parts[0] != "ov" || parts[1] == "" || parts[2] == "" {
		return "", "", false
	}
	return parts[1], parts[2], true
}

// topicVINMinLen 各 topic 家族的 VIN 长度下限。
// **统一取契约下限** `vehicle.VINMinLen`(5): 历史实现里 JSON 通道写 5、二进制通道写 4,
// 同一份 topic 契约两套判据 —— 现在两条通道同源, 且与 codec 侧新增的帧内 VIN 契约校验
// (VINContractReason) 使用同一组边界, 三条通道不再各判一套。
func topicVINMinLen(string) int { return vehicle.VINMinLen }
