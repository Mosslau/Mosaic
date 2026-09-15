package ratelimit

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

var okHandler = http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
	w.WriteHeader(http.StatusOK)
})

func requestWithToken(token string) *http.Request {
	r := httptest.NewRequest(http.MethodPost, "/api/v1/vehicle/report", nil)
	r.Header.Set("X-Device-Token", token)
	return r
}

func TestPerDeviceLimit(t *testing.T) {
	// 单设备 2/s, 全局足够大不干扰
	l := New(2, 100000)
	defer l.Close()
	h := l.Wrap(okHandler)

	// 单设备突发容量 = 速率 = 2, 前 2 个通过, 第 3 个 429
	for i := 1; i <= 2; i++ {
		w := httptest.NewRecorder()
		h.ServeHTTP(w, requestWithToken("dev-A"))
		if w.Code != http.StatusOK {
			t.Fatalf("第 %d 个请求应通过, 实际 %d", i, w.Code)
		}
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, requestWithToken("dev-A"))
	if w.Code != http.StatusTooManyRequests {
		t.Errorf("第 3 个请求应 429, 实际 %d", w.Code)
	}
	if w.Header().Get("Retry-After") == "" {
		t.Error("429 响应应带 Retry-After 头")
	}

	// 不同设备互不影响
	w = httptest.NewRecorder()
	h.ServeHTTP(w, requestWithToken("dev-B"))
	if w.Code != http.StatusOK {
		t.Errorf("另一台设备应不受 dev-A 限流影响, 实际 %d", w.Code)
	}
}

func TestGlobalLimit(t *testing.T) {
	// 全局 3/s(突发容量 2 倍=6), 单设备足够大不干扰
	l := New(100000, 3)
	defer l.Close()
	h := l.Wrap(okHandler)

	// 突发容量 6 内全通过
	for i := 1; i <= 6; i++ {
		w := httptest.NewRecorder()
		h.ServeHTTP(w, requestWithToken("any"))
		if w.Code != http.StatusOK {
			t.Fatalf("全局突发内第 %d 个应通过, 实际 %d", i, w.Code)
		}
	}
	// 超出突发容量 → 429
	w := httptest.NewRecorder()
	h.ServeHTTP(w, requestWithToken("any"))
	if w.Code != http.StatusTooManyRequests {
		t.Errorf("超出全局突发容量应 429, 实际 %d", w.Code)
	}
}

func TestTokenRefill(t *testing.T) {
	l := New(20, 100000) // 20/s → 50ms 补一个令牌
	defer l.Close()
	h := l.Wrap(okHandler)

	// 打空突发容量(20)
	for i := 0; i < 20; i++ {
		h.ServeHTTP(httptest.NewRecorder(), requestWithToken("dev-C"))
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, requestWithToken("dev-C"))
	if w.Code != http.StatusTooManyRequests {
		t.Fatalf("打空后应 429, 实际 %d", w.Code)
	}

	// 等 100ms 补约 2 个令牌, 应恢复通过
	time.Sleep(100 * time.Millisecond)
	w = httptest.NewRecorder()
	h.ServeHTTP(w, requestWithToken("dev-C"))
	if w.Code != http.StatusOK {
		t.Errorf("令牌补充后应恢复通过, 实际 %d", w.Code)
	}
}
