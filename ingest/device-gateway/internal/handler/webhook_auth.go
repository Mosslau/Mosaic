package handler

import (
	"crypto/subtle"
	"net/http"
	"strings"

	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/metrics"
	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/model"
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
func topicVIN(topic, suffix string, minLen int) (string, bool) {
	parts := strings.Split(topic, "/")
	if len(parts) != 3 || parts[0] != "ov" || parts[2] != suffix || len(parts[1]) < minLen {
		return "", false
	}
	return parts[1], true
}
