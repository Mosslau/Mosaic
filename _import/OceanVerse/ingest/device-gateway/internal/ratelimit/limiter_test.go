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
	l := New(2, 100000, 0)
	defer l.Close()
	h := l.Wrap(okHandler)

	// 单设备突发容量 = max(1, ceil(速率/2)) = 1(2026-09-20 收窄, 原为 = 速率):
	// 第 1 个通过, 第 2 个即 429 —— 单设备桶不再吸收惊群尖峰(那由全局桶兜)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, requestWithToken("dev-A"))
	if w.Code != http.StatusOK {
		t.Fatalf("第 1 个请求应通过, 实际 %d", w.Code)
	}
	w = httptest.NewRecorder()
	h.ServeHTTP(w, requestWithToken("dev-A"))
	if w.Code != http.StatusTooManyRequests {
		t.Errorf("第 2 个请求应 429(单设备 burst=1), 实际 %d", w.Code)
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
	// 全局 3/s, 显式突发容量 6, 单设备足够大不干扰
	l := New(100000, 3, 6)
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

// TestGlobalBurst_DefaultAndOverride 全局限流容量关系(2026-09-20 补):
// 未配置时 = defaultGlobalBurstFactor × 速率; 显式配置优先。
// 背景: 修复前硬编码 2× 速率, 一万设备按 1s 周期上报恰好 10000 qps = 正好打穿 burst,
// 于是"整队恢复上报"会被自己的全局限流拒掉。
func TestGlobalBurst_DefaultAndOverride(t *testing.T) {
	l := New(10, 5000, 0)
	if got := l.GlobalBurst(); got != int(5000*defaultGlobalBurstFactor) {
		t.Errorf("默认突发容量应为 %d×速率 = %d, 实际 %d", defaultGlobalBurstFactor, 5000*defaultGlobalBurstFactor, got)
	}
	l.Close()

	l2 := New(10, 5000, 12345)
	if got := l2.GlobalBurst(); got != 12345 {
		t.Errorf("显式配置应生效: 期望 12345, 实际 %d", got)
	}
	l2.Close()

	// 负值/非法视为未配置 → 回落默认公式(而不是造出 burst<=0 的"永久 429"桶)
	l3 := New(10, 100, -1)
	if got := l3.GlobalBurst(); got != 100*defaultGlobalBurstFactor {
		t.Errorf("非法容量应回落默认公式, 实际 %d", got)
	}
	l3.Close()
}

// TestPerDeviceBurst_HalfRate 单设备桶突发 = max(1, ceil(速率/2)), 且永不 >= 速率。
func TestPerDeviceBurst_HalfRate(t *testing.T) {
	cases := []struct {
		rate float64
		want int
	}{
		{1, 1}, {0.5, 1}, {10, 5}, {20, 10}, {3, 2},
	}
	for _, c := range cases {
		l := New(c.rate, 100000, 0)
		got := l.deviceLimiter("probe").Burst()
		l.Close()
		if got != c.want {
			t.Errorf("速率 %v 的单设备突发应为 %d, 实际 %d", c.rate, c.want, got)
		}
	}
}

func TestTokenRefill(t *testing.T) {
	l := New(20, 100000, 0) // 20/s → 50ms 补一个令牌; 单设备 burst = 10
	defer l.Close()
	h := l.Wrap(okHandler)

	// 打空单设备突发容量(10)
	for i := 0; i < 10; i++ {
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
