// 来源：ph16-pgo-advanced-perf 综合项目（apiserver 的 handler 单测 + 签名核心 benchmark）
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 运行：go test ./...；go test -bench=BenchmarkSignDevice -run='^$' -benchmem -count=6 ./cmd/apiserver
// 验证状态：已验证（go1.25.6，2026-09-02）
package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func newTestDevs() []*Device { return newDevices(50, 1024) }

func TestHealthz(t *testing.T) {
	req := httptest.NewRequest("GET", "/healthz", nil)
	rec := httptest.NewRecorder()
	handleHealthz(rec, req)
	if rec.Code != http.StatusOK || !strings.Contains(rec.Body.String(), `"ok"`) {
		t.Fatalf("healthz = %d %s", rec.Code, rec.Body.String())
	}
}

func TestDeviceHandler(t *testing.T) {
	devs := newTestDevs()
	h := handleDevice(devs)

	req := httptest.NewRequest("GET", "/api/devices/7", nil)
	rec := httptest.NewRecorder()
	h(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("code = %d, body = %s", rec.Code, rec.Body.String())
	}
	var body struct {
		ID      int    `json:"id"`
		Name    string `json:"name"`
		Samples int    `json:"samples"`
		Digest  string `json:"digest"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("响应不是合法 JSON: %v", err)
	}
	if body.ID != 7 || body.Name != "device-00007" || body.Samples != 1024 {
		t.Fatalf("响应字段不对: %+v", body)
	}

	// 同一设备两次请求 digest 必须一致（确定性签名）
	rec2 := httptest.NewRecorder()
	h(rec2, req)
	if !strings.Contains(rec2.Body.String(), body.Digest) {
		t.Fatalf("digest 不确定: %s vs %s", rec2.Body.String(), rec.Body.String())
	}
}

func TestDeviceHandlerNotFound(t *testing.T) {
	devs := newTestDevs()
	h := handleDevice(devs)
	for _, p := range []string{"/api/devices/", "/api/devices/abc", "/api/devices/9999", "/api/devices/-1"} {
		req := httptest.NewRequest("GET", p, nil)
		rec := httptest.NewRecorder()
		h(rec, req)
		if rec.Code != http.StatusNotFound {
			t.Fatalf("%s → %d, want 404", p, rec.Code)
		}
	}
}

func TestSignerMix(t *testing.T) {
	fnv := &fnvSigner{A: 3, C: 1}
	if fnv.Step(5) != 16 {
		t.Fatalf("fnvSigner.Step(5) = %d, want 16", fnv.Step(5))
	}
	xor := &xorSigner{}
	if xor.Step(0) != 0 {
		t.Fatalf("xorSigner.Step(0) = %d, want 0", xor.Step(0))
	}
}

func TestSignDeviceDeterministic(t *testing.T) {
	devs := newTestDevs()
	a := signDevice(devs[0])
	b := signDevice(devs[0])
	if a != b {
		t.Fatalf("signDevice 不确定: %x != %x", a, b)
	}
	if a == signDevice(devs[1]) {
		t.Fatal("不同设备得到相同签名")
	}
}

// BenchmarkSignDevice 是签名核心基准：scripts/regress.sh 的性能回归对象。
// signDevice 走接口分派，PGO 前后差异在此可被 -bench 稳定量化。
func BenchmarkSignDevice(b *testing.B) {
	devs := newDevices(1, 8192)
	d := devs[0]
	b.ReportAllocs()
	b.SetBytes(8192 * 8)
	var sink uint64
	for i := 0; i < b.N; i++ {
		sink ^= signDevice(d)
	}
	_ = sink
}
