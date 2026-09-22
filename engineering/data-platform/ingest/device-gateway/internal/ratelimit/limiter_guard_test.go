package ratelimit

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestBurstFor_NeverZero 令牌桶容量必须 >= 1。
// 背景(2026-09-18 审计实测): 速率 <1 时 int(rate) 截断为 0, 而 x/time/rate
// 在 burst==0 时 AllowN 恒返回 false → 所有请求永久 429, 服务等于全灭。
func TestBurstFor_NeverZero(t *testing.T) {
	for _, perSec := range []float64{0.1, 0.5, 0.9, 1, 1.5, 10, 5000} {
		if got := burstFor(perSec, 1); got < 1 {
			t.Errorf("burstFor(%v, 1) = %d, 必须 >= 1", perSec, got)
		}
		if got := burstFor(perSec, 2); got < 1 {
			t.Errorf("burstFor(%v, 2) = %d, 必须 >= 1", perSec, got)
		}
	}
	// 正常速率仍按 rate×factor 向上取整
	if got := burstFor(10, 1); got != 10 {
		t.Errorf("burstFor(10,1) 应为 10, 实际 %d", got)
	}
	if got := burstFor(0.5, 2); got != 1 {
		t.Errorf("burstFor(0.5,2) 应为 1, 实际 %d", got)
	}
}

// TestLimiter_FractionalRateNotFullyRejected 小数速率不再导致"全量 429"。
func TestLimiter_FractionalRateNotFullyRejected(t *testing.T) {
	l := New(0.5, 5000, 0) // 修复前: perDevice=0.5 → burst=0 → 每个请求都 429
	defer l.Close()

	next := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusOK) })
	h := l.Wrap(next)

	// 首个请求应被放行(桶初始满, 容量至少 1)
	r := httptest.NewRequest(http.MethodPost, "/x", nil)
	r.Header.Set("X-Device-Token", "t1")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)

	if w.Code == http.StatusTooManyRequests {
		t.Fatal("小数速率下首个请求不应被拒(修复前 burst=0 导致全量 429)")
	}
}

// TestLimiter_GlobalWrap_OnlyGlobalBucket 全局桶可被限流, 且不建单设备桶。
func TestLimiter_GlobalWrap_OnlyGlobalBucket(t *testing.T) {
	l := New(10, 1, 2) // 全局 1/s, burst=2(显式)
	defer l.Close()

	next := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusOK) })
	h := l.GlobalWrap(next)

	codes := make([]int, 0, 4)
	for i := 0; i < 4; i++ {
		r := httptest.NewRequest(http.MethodPost, "/x", nil)
		r.Header.Set("X-Device-Token", "whatever")
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		codes = append(codes, w.Code)
	}
	// burst=2 + 令牌补充: 前几个放行, 后续必有限流
	sawLimited := false
	for _, c := range codes {
		if c == http.StatusTooManyRequests {
			sawLimited = true
		}
	}
	if !sawLimited {
		t.Fatalf("全局桶应限流, 实际状态码序列 %v", codes)
	}
	// GlobalWrap 不得为请求头建单设备桶
	l.mu.Lock()
	n := len(l.devices)
	l.mu.Unlock()
	if n != 0 {
		t.Errorf("GlobalWrap 不应创建单设备桶, 实际 %d 个", n)
	}
}

// TestLimiter_CloseIdempotent 重复 Close 不得 panic。
func TestLimiter_CloseIdempotent(t *testing.T) {
	l := New(10, 100, 0)
	l.Close()
	l.Close() // 修复前: panic: close of closed channel
}

// TestLimiter_DeviceMapBounded 设备桶 map 到达上限后不再增长(dev 模式防内存打爆)。
func TestLimiter_DeviceMapBounded(t *testing.T) {
	l := New(10, 100000, 0)
	defer l.Close()

	l.mu.Lock()
	for i := 0; i < maxDeviceKeys; i++ {
		l.devices[fmt.Sprintf("dev-%d", i)] = &deviceEntry{}
	}
	l.mu.Unlock()

	// 已达上限: 新 key 不应再建桶
	next := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusOK) })
	h := l.Wrap(next)
	r := httptest.NewRequest(http.MethodPost, "/x", nil)
	r.Header.Set("X-Device-Token", "brand-new-key")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)

	l.mu.Lock()
	n := len(l.devices)
	l.mu.Unlock()
	if n != maxDeviceKeys {
		t.Errorf("设备桶数量不应超过上限 %d, 实际 %d", maxDeviceKeys, n)
	}
}
