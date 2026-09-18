package handler

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// TestMQTTIngest_VINMismatchRejected 载荷 VIN 与 topic VIN 不一致必须拒绝。
// 背景(2026-09-18 审计): EMQX ACL 只约束"能发哪个 topic", 不约束 payload 内容。
// 修复前载荷 VIN 会覆盖 topic VIN 并作为 Kafka key → 任何持合法凭证的设备
// 都能以他人 VIN 写入数据(污染他人车辆画像/告警), 等于绕过 ACL。
func TestMQTTIngest_VINMismatchRejected(t *testing.T) {
	fs := &fakeSender{}
	h := NewMQTTIngestHandler(fs, testWebhookToken)

	// 设备 OV00000001 发到自己的 topic, 但载荷声称是 OV99999999
	payload := fmt.Sprintf(`{"vin":"OV99999999","ts":%d,"type":"vehicle_status","data":{"soc":80}}`, time.Now().Unix())
	w := mqttPost(t, h, testWebhookToken, emqxEnvelope("dev-OV00000001", "ov/OV00000001/status", payload))

	if w.Code != http.StatusBadRequest {
		t.Fatalf("载荷 VIN 与 topic 不一致应 400, 实际 %d, body=%s", w.Code, w.Body)
	}
	if len(fs.messages) != 0 {
		t.Fatalf("不一致的消息绝不能投递, 实际投递 %+v", fs.messages)
	}
	if !strings.Contains(w.Body.String(), "vin") {
		t.Errorf("错误信息应指明 vin 不一致, 实际 %s", w.Body)
	}
}

// TestMQTTIngest_VINFromTopicWhenAbsent 载荷没带 VIN 时按 topic 回填(原有行为不能破)。
func TestMQTTIngest_VINFromTopicWhenAbsent(t *testing.T) {
	fs := &fakeSender{}
	h := NewMQTTIngestHandler(fs, testWebhookToken)

	payload := fmt.Sprintf(`{"ts":%d,"type":"vehicle_status","data":{"soc":80}}`, time.Now().Unix())
	w := mqttPost(t, h, testWebhookToken, emqxEnvelope("dev-OV00000001", "ov/OV00000001/status", payload))

	if w.Code != http.StatusNoContent {
		t.Fatalf("VIN 缺失应按 topic 回填并受理(204), 实际 %d, body=%s", w.Code, w.Body)
	}
	if len(fs.messages) != 1 || fs.messages[0].key != "OV00000001" {
		t.Fatalf("应按 topic VIN 投递, 实际 %+v", fs.messages)
	}
}

// TestMQTTIngest_VINMatchAccepted 载荷 VIN 与 topic 一致时正常受理(正例)。
func TestMQTTIngest_VINMatchAccepted(t *testing.T) {
	fs := &fakeSender{}
	h := NewMQTTIngestHandler(fs, testWebhookToken)

	payload := fmt.Sprintf(`{"vin":"OV00000001","ts":%d,"type":"vehicle_status","data":{"soc":80}}`, time.Now().Unix())
	w := mqttPost(t, h, testWebhookToken, emqxEnvelope("OV00000001", "ov/OV00000001/status", payload))

	if w.Code != http.StatusNoContent {
		t.Fatalf("VIN 一致应受理 204, 实际 %d, body=%s", w.Code, w.Body)
	}
}

// TestBinIngest_WebhookAuthConstantTime 二进制通道同样必须校验 webhook 密钥。
func TestBinIngest_WebhookAuth(t *testing.T) {
	fs := &fakeSender{}
	h := NewBinIngestHandler(fs, testWebhookToken)

	body := fmt.Sprintf(`{"clientid":"dev-OV00000001","topic":"ov/OV00000001/bin","ts":%d,"payload_b64":"IyM="}`, time.Now().UnixMilli())
	for _, tc := range []struct {
		name  string
		token string
		want  int
	}{
		{"正确密钥", testWebhookToken, http.StatusNoContent},
		{"错误密钥", "wrong", http.StatusUnauthorized},
		{"空密钥", "", http.StatusUnauthorized},
		{"前缀相同的密钥", testWebhookToken[:len(testWebhookToken)-1], http.StatusUnauthorized},
	} {
		t.Run(tc.name, func(t *testing.T) {
			r := httptest.NewRequest(http.MethodPost, "/api/v1/bin/ingest", strings.NewReader(body))
			r.Header.Set("X-Webhook-Token", tc.token)
			w := httptest.NewRecorder()
			http.HandlerFunc(h.IngestBin).ServeHTTP(w, r)
			if w.Code != tc.want {
				t.Fatalf("期望 %d, 实际 %d, body=%s", tc.want, w.Code, w.Body)
			}
		})
	}
}

// TestBinIngest_TopicVINBoundToEnvelope 信封里的 VIN 必须来自 topic(而非 clientid)。
func TestBinIngest_TopicVINBoundToEnvelope(t *testing.T) {
	fs := &fakeSender{}
	h := NewBinIngestHandler(fs, testWebhookToken)

	body := fmt.Sprintf(`{"clientid":"OV00000001","topic":"ov/OV20260001/bin","ts":%d,"payload_b64":"IyM="}`, time.Now().UnixMilli())
	r := httptest.NewRequest(http.MethodPost, "/api/v1/bin/ingest", strings.NewReader(body))
	r.Header.Set("X-Webhook-Token", testWebhookToken)
	w := httptest.NewRecorder()
	http.HandlerFunc(h.IngestBin).ServeHTTP(w, r)

	if w.Code != http.StatusNoContent {
		t.Fatalf("期望 204, 实际 %d, body=%s", w.Code, w.Body)
	}
	if len(fs.messages) != 1 || fs.messages[0].key != "OV20260001" {
		t.Fatalf("信封 VIN 必须取 topic 的 OV20260001, 实际 %+v", fs.messages)
	}
}
