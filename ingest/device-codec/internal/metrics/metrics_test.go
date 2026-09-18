package metrics

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// TestHealth 健康探针: 200 + status=up(供 K8s liveness/readiness 使用)
func TestHealth(t *testing.T) {
	rec := httptest.NewRecorder()
	Handler().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/health", nil))

	if rec.Code != http.StatusOK {
		t.Fatalf("应 200, 实际 %d", rec.Code)
	}
	var got map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("/health 应为 JSON: %v (body=%s)", err, rec.Body)
	}
	if got["status"] != "up" {
		t.Errorf("status 应 up, 实际 %v", got["status"])
	}
	if _, ok := got["lag"]; !ok {
		t.Error("/health 应带 lag 字段(排障时一眼看到积压)")
	}
}

// TestMetrics 指标端点: 暴露 codec_ 前缀的关键指标(消费/解码/DLQ/lag/flush)
func TestMetrics(t *testing.T) {
	ConsumedTotal.Add(2)
	DecodedTotal.WithLabelValues("vehicle_status").Inc()
	DLQTotal.WithLabelValues("parse").Inc()

	rec := httptest.NewRecorder()
	Handler().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/metrics", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("/metrics 应 200, 实际 %d", rec.Code)
	}
	body := rec.Body.String()
	for _, name := range []string{
		"codec_consumed_total",
		"codec_decoded_total",
		"codec_dlq_total",
		"codec_consumer_lag",
		"codec_flush_duration_seconds",
		"codec_flush_batch_size",
	} {
		if !strings.Contains(body, name) {
			t.Errorf("/metrics 应包含 %s", name)
		}
	}
	if !strings.Contains(body, `stage="parse"`) {
		t.Error("DLQ 指标应带 stage 标签")
	}
}
