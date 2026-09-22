package handler

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/auth"
	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/metrics"
	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/model"
)

// 本文件覆盖"载荷 VIN 必须与 token 绑定的设备身份一致"(2026-09-18 审计补齐)。
// 走**真实中间件链**(auth.Wrap → Report), 而不是直接调 handler ——
// 身份是 Wrap 注入 context 的, 绕过 Wrap 的测试恰好证明不了这道防线存在。

// identityChain 构造 auth.Wrap(Report) 的真链。
func identityChain(fs *fakeSender, bindings map[string]string, devMode bool) http.Handler {
	return auth.New(bindings, devMode).Wrap(http.HandlerFunc(NewReportHandler(fs).Report))
}

// postWithToken 带设备 token 发一条上报。
func postWithToken(h http.Handler, token, body string) *httptest.ResponseRecorder {
	r := httptest.NewRequest(http.MethodPost, "/api/v1/vehicle/report", strings.NewReader(body))
	if token != "" {
		r.Header.Set(auth.TokenHeader, token)
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	return w
}

// TestReport_IdentityMatchAccepted 载荷 VIN == 绑定 VIN → 正常受理(回归保护)。
func TestReport_IdentityMatchAccepted(t *testing.T) {
	fs := &fakeSender{}
	h := identityChain(fs, map[string]string{"token-a": "OV20260001"}, false)

	w := postWithToken(h, "token-a", validBody()) // validBody 的 vin = OV20260001
	if w.Code != http.StatusAccepted {
		t.Fatalf("身份一致应 202, 实际 %d, body=%s", w.Code, w.Body)
	}
	if len(fs.messages) != 1 {
		t.Fatalf("应投递 1 条, 实际 %d", len(fs.messages))
	}
}

// TestReport_VINMismatchRejected 载荷填他人 VIN → 400 且**一条都不投递**。
// 修复前: 用自己 token 上报他人 VIN 会被受理, 数据以他人 VIN 落 Kafka(冒充他人车辆)。
func TestReport_VINMismatchRejected(t *testing.T) {
	fs := &fakeSender{}
	h := identityChain(fs, map[string]string{"token-a": "OV20260001"}, false)

	victim := fmt.Sprintf(`{"vin":"OV99999999","ts":%d,"type":"vehicle_status","data":{"soc":50}}`, time.Now().Unix())
	w := postWithToken(h, "token-a", victim)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("冒充他人 VIN 应 400, 实际 %d, body=%s", w.Code, w.Body)
	}
	if !strings.Contains(w.Body.String(), string(model.CodeInvalidData)) {
		t.Errorf("错误码应为 INVALID_DATA, body=%s", w.Body)
	}
	if len(fs.messages) != 0 {
		t.Fatalf("冒充他人 VIN 不得投递 Kafka, 实际 %d 条: %+v", len(fs.messages), fs.messages)
	}
	// 两个 VIN 都要出现在错误里(便于设备端与运维定位)
	if !strings.Contains(w.Body.String(), "OV20260001") || !strings.Contains(w.Body.String(), "OV99999999") {
		t.Errorf("错误消息应含绑定 VIN 与载荷 VIN, body=%s", w.Body)
	}
}

// TestReport_VINMismatchMetric 该拒绝必须计入 result="vin_mismatch" ——
// 告警规则 ⑧(GatewayVINMismatch)的表达式就盯这个标签, 标签名变了告警就静默失效。
func TestReport_VINMismatchMetric(t *testing.T) {
	fs := &fakeSender{}
	h := identityChain(fs, map[string]string{"token-a": "OV20260001"}, false)
	postWithToken(h, "token-a",
		fmt.Sprintf(`{"vin":"OV99999999","ts":%d,"type":"vehicle_status","data":{"soc":50}}`, time.Now().Unix()))

	mux := http.NewServeMux()
	metrics.RegisterMetrics(mux)
	req := httptest.NewRequest(http.MethodGet, "/metrics", nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)

	if !strings.Contains(rec.Body.String(), `result="vin_mismatch"`) {
		t.Error("越权拒绝必须计入 gateway_requests_total{result=\"vin_mismatch\"}(告警规则 ⑧ 依赖该标签)")
	}
}

// TestReport_DevModeStillChecksVIN dev 模式必须**仍然**校验 VIN:
// 旧实现放行任意 "dev-" 前缀且不校验, 等于给 VIN 校验留了后门。
func TestReport_DevModeStillChecksVIN(t *testing.T) {
	// dev-{VIN} 与载荷一致 → 受理
	fs := &fakeSender{}
	h := identityChain(fs, nil, true)
	if w := postWithToken(h, "dev-OV20260001", validBody()); w.Code != http.StatusAccepted {
		t.Fatalf("dev 模式身份一致应 202, 实际 %d, body=%s", w.Code, w.Body)
	}

	// dev-{VIN} 与载荷不一致 → 拒绝
	fs2 := &fakeSender{}
	h2 := identityChain(fs2, nil, true)
	w := postWithToken(h2, "dev-OV11111111", validBody()) // 载荷 VIN 是 OV20260001
	if w.Code != http.StatusBadRequest {
		t.Fatalf("dev 模式身份不一致应 400, 实际 %d, body=%s", w.Code, w.Body)
	}
	if len(fs2.messages) != 0 {
		t.Error("dev 模式越权也不得投递")
	}
}
