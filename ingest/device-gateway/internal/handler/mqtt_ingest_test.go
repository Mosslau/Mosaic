package handler

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

const testWebhookToken = "test-secret"

func emqxEnvelope(clientID, topic string, payload string) string {
	return fmt.Sprintf(`{"clientid":%q,"topic":%q,"qos":1,"ts":%d,"payload":%s}`,
		clientID, topic, time.Now().UnixMilli(), payload)
}

func mqttPost(t *testing.T, h *MQTTIngestHandler, token, body string) *httptest.ResponseRecorder {
	t.Helper()
	r := httptest.NewRequest(http.MethodPost, "/api/v1/mqtt/ingest", strings.NewReader(body))
	r.Header.Set("X-Webhook-Token", token)
	w := httptest.NewRecorder()
	http.HandlerFunc(h.Ingest).ServeHTTP(w, r)
	return w
}

func TestMQTTIngest_OK(t *testing.T) {
	fs := &fakeSender{}
	h := NewMQTTIngestHandler(fs, testWebhookToken)

	payload := fmt.Sprintf(`{"vin":"OV00000001","ts":%d,"type":"vehicle_status","data":{"soc":80}}`, time.Now().Unix())
	w := mqttPost(t, h, testWebhookToken, emqxEnvelope("dev-OV00000001", "ov/OV00000001/status", payload))

	if w.Code != http.StatusNoContent {
		t.Fatalf("期望 204, 实际 %d, body=%s", w.Code, w.Body)
	}
	if len(fs.messages) != 1 || fs.messages[0].key != "OV00000001" {
		t.Fatalf("应按 VIN 投递 1 条, 实际 %+v", fs.messages)
	}
}

func TestMQTTIngest_WebhookAuth(t *testing.T) {
	fs := &fakeSender{}
	h := NewMQTTIngestHandler(fs, testWebhookToken)

	payload := fmt.Sprintf(`{"vin":"OV00000001","ts":%d,"type":"vehicle_status"}`, time.Now().Unix())
	env := emqxEnvelope("dev-OV00000001", "ov/OV00000001/status", payload)

	// 错误密钥 → 401
	w := mqttPost(t, h, "wrong-token", env)
	if w.Code != http.StatusUnauthorized {
		t.Errorf("错误 webhook 密钥应 401, 实际 %d", w.Code)
	}
	// 空密钥 → 401
	w = mqttPost(t, h, "", env)
	if w.Code != http.StatusUnauthorized {
		t.Errorf("空 webhook 密钥应 401, 实际 %d", w.Code)
	}
	if len(fs.messages) != 0 {
		t.Error("鉴权失败不应投递 Kafka")
	}
}

// 契约回填: 载荷缺 vin/type 时按 topic ov/{vin}/{type} 推断
func TestMQTTIngest_TopicBackfill(t *testing.T) {
	fs := &fakeSender{}
	h := NewMQTTIngestHandler(fs, testWebhookToken)

	// 载荷不带 vin/type, 由 topic 回填
	payload := fmt.Sprintf(`{"ts":%d,"data":{"soc":66}}`, time.Now().Unix())
	env := emqxEnvelope("dev-OV777", "ov/OV77777/battery", payload)

	w := mqttPost(t, h, testWebhookToken, env)
	if w.Code != http.StatusNoContent {
		t.Fatalf("topic 回填后应通过, 实际 %d, body=%s", w.Code, w.Body)
	}
	if fs.messages[0].key != "OV77777" {
		t.Errorf("VIN 应从 topic 回填为 OV77777, 实际 key=%q", fs.messages[0].key)
	}
}

func TestMQTTIngest_InvalidPayload(t *testing.T) {
	fs := &fakeSender{}
	h := NewMQTTIngestHandler(fs, testWebhookToken)

	// 载荷不是 JSON
	w := mqttPost(t, h, testWebhookToken, emqxEnvelope("c", "ov/OV1/status", `"broken"`))
	if w.Code != http.StatusBadRequest {
		t.Errorf("载荷非法应 400, 实际 %d", w.Code)
	}
}

func TestMQTTIngest_KafkaError_Retries(t *testing.T) {
	// Kafka 故障返回 500, EMQX 凭 5xx 重试
	fs := &fakeSender{err: errKafka}
	h := NewMQTTIngestHandler(fs, testWebhookToken)

	payload := fmt.Sprintf(`{"vin":"OV00000001","ts":%d,"type":"vehicle_status"}`, time.Now().Unix())
	w := mqttPost(t, h, testWebhookToken, emqxEnvelope("dev-OV00000001", "ov/OV00000001/status", payload))
	if w.Code != http.StatusInternalServerError {
		t.Errorf("Kafka 故障应 500(触发 EMQX 重试), 实际 %d", w.Code)
	}
}

var errKafka = errorString("kafka down")

type errorString string

func (e errorString) Error() string { return string(e) }
