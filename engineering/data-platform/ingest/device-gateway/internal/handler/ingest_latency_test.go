package handler

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/Mosslau/Mosaic/ingest/device-gateway/internal/metrics"
)

// 本文件锁定上行延迟 SLI(《接入层设计》§9 的"分段延迟之间没有桥"):
// gateway_ingest_latency_seconds = EMQX 接收(毫秒时间戳) → 网关受理完成。
// 关键点: 它必须出现在**受理成功**的两个 webhook 通道上, 且时间戳缺失时不能观测
// (噪声样本会污染分位数)。

// scrapeMetrics 取一次 /metrics 文本。
func scrapeMetrics(t *testing.T) string {
	t.Helper()
	mux := http.NewServeMux()
	metrics.RegisterMetrics(mux)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/metrics", nil))
	return rec.Body.String()
}

// countOf 从指标文本里取某条 series 的 _count 值; 不存在返回 -1。
func countOf(t *testing.T, body, series string) float64 {
	t.Helper()
	for _, line := range strings.Split(body, "\n") {
		if strings.HasPrefix(line, series+" ") {
			var v float64
			if _, err := fmt.Sscanf(line, series+" %g", &v); err != nil {
				t.Fatalf("解析指标行失败 %q: %v", line, err)
			}
			return v
		}
	}
	return -1
}

func TestIngestLatency_MQTTChannelObserved(t *testing.T) {
	fs := &fakeSender{}
	h := NewMQTTIngestHandler(fs, testWebhookToken)

	payload := fmt.Sprintf(`{"vin":"OV00000001","ts":%d,"type":"vehicle_status","data":{"soc":80}}`, time.Now().Unix())
	w := mqttPost(t, h, testWebhookToken, emqxEnvelope("dev-OV00000001", "ov/OV00000001/status", payload))
	if w.Code != http.StatusNoContent {
		t.Fatalf("期望 204, 实际 %d, body=%s", w.Code, w.Body)
	}

	got := countOf(t, scrapeMetrics(t), `gateway_ingest_latency_seconds_count{channel="mqtt"}`)
	if got < 1 {
		t.Errorf("受理成功后应观测到 channel=mqtt 的上行延迟样本, 实际 count=%v", got)
	}
}

func TestIngestLatency_BinChannelObserved(t *testing.T) {
	fs := &fakeSender{}
	h := NewBinIngestHandler(fs, testWebhookToken)

	body := fmt.Sprintf(`{"clientid":"dev-OV00000001","topic":"ov/OV00000001/bin","ts":%d,"payload_b64":"IyM="}`,
		time.Now().UnixMilli())
	r := httptest.NewRequest(http.MethodPost, "/api/v1/bin/ingest", strings.NewReader(body))
	r.Header.Set("X-Webhook-Token", testWebhookToken)
	w := httptest.NewRecorder()
	http.HandlerFunc(h.IngestBin).ServeHTTP(w, r)
	if w.Code != http.StatusNoContent {
		t.Fatalf("期望 204, 实际 %d, body=%s", w.Code, w.Body)
	}

	got := countOf(t, scrapeMetrics(t), `gateway_ingest_latency_seconds_count{channel="bin"}`)
	if got < 1 {
		t.Errorf("受理成功后应观测到 channel=bin 的上行延迟样本, 实际 count=%v", got)
	}
}

// TestIngestLatency_MissingTimestampNotObserved 信封时间戳缺失(<=0)时必须**不观测**。
// 否则一条 "ts=0" 的异常消息会给直方图灌进一个约 56 年的样本, 把 p99 永久拉飞。
func TestIngestLatency_MissingTimestampNotObserved(t *testing.T) {
	before := countOf(t, scrapeMetrics(t), `gateway_ingest_latency_seconds_count{channel="mqtt"}`)
	if before < 0 {
		before = 0
	}

	fs := &fakeSender{}
	h := NewMQTTIngestHandler(fs, testWebhookToken)
	payload := fmt.Sprintf(`{"vin":"OV00000001","ts":%d,"type":"vehicle_status","data":{"soc":80}}`, time.Now().Unix())
	// ts=0: 模拟 EMQX 规则未取 timestamp
	body := fmt.Sprintf(`{"clientid":"dev-OV00000001","topic":"ov/OV00000001/status","qos":1,"ts":0,"payload":%s}`, payload)
	w := mqttPost(t, h, testWebhookToken, body)
	if w.Code != http.StatusNoContent {
		t.Fatalf("时间戳缺失不应影响受理, 实际 %d", w.Code)
	}

	after := countOf(t, scrapeMetrics(t), `gateway_ingest_latency_seconds_count{channel="mqtt"}`)
	if after != before {
		t.Errorf("时间戳缺失时不得观测: before=%v after=%v", before, after)
	}
}
