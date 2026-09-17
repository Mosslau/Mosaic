package handler

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/Mosslau/OceanVerse/ingest/device-contracts/vehicle"
	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/model"
)

// fakeSender 可控的 Sender 实现: 记录投递内容, 可注入错误
type fakeSender struct {
	err      error
	messages []fakeMessage
}

type fakeMessage struct {
	key     string
	payload string
}

func (f *fakeSender) WriteReport(_ context.Context, key, payload []byte) error {
	if f.err != nil {
		return f.err
	}
	f.messages = append(f.messages, fakeMessage{key: string(key), payload: string(payload)})
	return nil
}

func validBody() string {
	return fmt.Sprintf(`{"vin":"OV20260001","ts":%d,"type":"vehicle_status","data":{"speed":32.5,"soc":78}}`,
		time.Now().Unix())
}

func post(t *testing.T, h http.Handler, body string) *httptest.ResponseRecorder {
	t.Helper()
	r := httptest.NewRequest(http.MethodPost, "/api/v1/vehicle/report", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	return w
}

func TestReport_OK(t *testing.T) {
	fs := &fakeSender{}
	h := NewReportHandler(fs)

	w := post(t, http.HandlerFunc(h.Report), validBody())
	if w.Code != http.StatusAccepted {
		t.Fatalf("期望 202, 实际 %d, body=%s", w.Code, w.Body)
	}
	if len(fs.messages) != 1 {
		t.Fatalf("应投递 1 条消息, 实际 %d", len(fs.messages))
	}
	// Kafka key 应为 VIN(保序契约)
	if fs.messages[0].key != "OV20260001" {
		t.Errorf("Kafka key 应为 VIN, 实际 %q", fs.messages[0].key)
	}
	// payload 应可解析回契约
	var r vehicle.VehicleReport
	if err := json.Unmarshal([]byte(fs.messages[0].payload), &r); err != nil {
		t.Errorf("投递 payload 应为合法契约 JSON: %v", err)
	}
}

func TestReport_MethodNotAllowed(t *testing.T) {
	fs := &fakeSender{}
	h := NewReportHandler(fs)
	r := httptest.NewRequest(http.MethodGet, "/api/v1/vehicle/report", nil)
	w := httptest.NewRecorder()
	http.HandlerFunc(h.Report).ServeHTTP(w, r)
	if w.Code != http.StatusMethodNotAllowed {
		t.Errorf("GET 应 405, 实际 %d", w.Code)
	}
}

func TestReport_InvalidJSON(t *testing.T) {
	fs := &fakeSender{}
	h := NewReportHandler(fs)
	w := post(t, http.HandlerFunc(h.Report), `{not json`)
	if w.Code != http.StatusBadRequest {
		t.Errorf("非法 JSON 应 400, 实际 %d", w.Code)
	}
	if !strings.Contains(w.Body.String(), string(model.CodeInvalidBody)) {
		t.Errorf("错误码应为 INVALID_BODY, body=%s", w.Body)
	}
	if len(fs.messages) != 0 {
		t.Error("非法请求不应投递 Kafka")
	}
}

func TestReport_InvalidData(t *testing.T) {
	fs := &fakeSender{}
	h := NewReportHandler(fs)
	// soc=300 越界
	body := fmt.Sprintf(`{"vin":"OV20260001","ts":%d,"type":"vehicle_status","data":{"soc":300}}`, time.Now().Unix())
	w := post(t, http.HandlerFunc(h.Report), body)
	if w.Code != http.StatusBadRequest {
		t.Errorf("越界数据应 400, 实际 %d", w.Code)
	}
	if !strings.Contains(w.Body.String(), string(model.CodeInvalidData)) {
		t.Errorf("错误码应为 INVALID_DATA, body=%s", w.Body)
	}
	if !strings.Contains(w.Body.String(), "soc") {
		t.Errorf("错误消息应含具体原因, body=%s", w.Body)
	}
}

func TestReport_KafkaError(t *testing.T) {
	fs := &fakeSender{err: errors.New("broker down")}
	h := NewReportHandler(fs)
	w := post(t, http.HandlerFunc(h.Report), validBody())
	if w.Code != http.StatusInternalServerError {
		t.Errorf("Kafka 故障应 500, 实际 %d", w.Code)
	}
}
