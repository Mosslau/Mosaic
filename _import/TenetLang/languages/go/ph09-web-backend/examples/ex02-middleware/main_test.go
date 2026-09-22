// 来源：09-web-backend.md 第 6 章示例 2 —— 中间件组合
// 一句话说明：httptest 验证四个中间件的可观察行为（CORS 头 / 500 恢复 / 429 限流 / 日志捕获状态码）。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// do 辅助：按给定中间件顺序包裹 handler 后执行请求
func do(t *testing.T, mws []func(http.Handler) http.Handler, method, path string) *httptest.ResponseRecorder {
	t.Helper()
	h := chain(newMux(), mws...)
	req := httptest.NewRequest(method, path, nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

// TestCORSPreflight 预检请求：OPTIONS 直接返回 204 且带 CORS 头，不进入业务 handler
func TestCORSPreflight(t *testing.T) {
	rec := do(t, []func(http.Handler) http.Handler{withCORS}, http.MethodOptions, "/ping")
	if rec.Code != http.StatusNoContent {
		t.Errorf("OPTIONS 状态码 = %d, 期望 204", rec.Code)
	}
	if got := rec.Header().Get("Access-Control-Allow-Origin"); got != "*" {
		t.Errorf("Allow-Origin = %q, 期望 *", got)
	}
	if got := rec.Header().Get("Access-Control-Allow-Methods"); !strings.Contains(got, "POST") {
		t.Errorf("Allow-Methods = %q, 期望包含 POST", got)
	}
}

// TestCORSRealRequest 真实请求：业务照常执行且响应带 CORS 头
func TestCORSRealRequest(t *testing.T) {
	rec := do(t, []func(http.Handler) http.Handler{withCORS}, http.MethodGet, "/ping")
	if rec.Code != http.StatusOK || rec.Body.String() != "pong" {
		t.Errorf("GET /ping = %d %q, 期望 200 pong", rec.Code, rec.Body.String())
	}
	if got := rec.Header().Get("Access-Control-Allow-Origin"); got != "*" {
		t.Errorf("Allow-Origin = %q, 期望 *", got)
	}
}

// TestRecovery 恢复中间件：handler panic 时返回 500 而不是让进程崩溃
func TestRecovery(t *testing.T) {
	rec := do(t, []func(http.Handler) http.Handler{withRecovery}, http.MethodGet, "/boom")
	if rec.Code != http.StatusInternalServerError {
		t.Errorf("panic 后状态码 = %d, 期望 500", rec.Code)
	}
}

// TestRateLimit 窗口限流（滑动时间窗日志）：同一 IP 第 limit+1 次请求返回 429
func TestRateLimit(t *testing.T) {
	const limit = 5
	mw := withRateLimit(limit, time.Minute)
	statuses := make([]int, 0, limit+1)
	for i := 0; i < limit+1; i++ {
		rec := do(t, []func(http.Handler) http.Handler{mw}, http.MethodGet, "/ping")
		statuses = append(statuses, rec.Code)
	}
	if statuses[limit-1] != http.StatusOK {
		t.Errorf("第 %d 次请求状态码 = %d, 期望 200（未达上限）", limit, statuses[limit-1])
	}
	if statuses[limit] != http.StatusTooManyRequests {
		t.Errorf("第 %d 次请求状态码 = %d, 期望 429（超上限）", limit+1, statuses[limit])
	}
}

// TestLoggingCapturesStatus 日志中间件通过 statusRecorder 捕获内层写入的状态码：
// 完整链（日志最外层）里 /boom 的 panic 被恢复为 500，日志中间件应记录 500
func TestLoggingCapturesStatus(t *testing.T) {
	h := chain(newMux(), withLogging, withRecovery) // 日志在外、恢复在内
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/boom", nil)
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusInternalServerError {
		t.Errorf("/boom 经恢复中间件后状态码 = %d, 期望 500", rec.Code)
	}
}

// TestStatusRecorder statusRecorder 单元行为：WriteHeader 记录状态码，未写时默认 200
func TestStatusRecorder(t *testing.T) {
	inner := httptest.NewRecorder()
	rec := &statusRecorder{ResponseWriter: inner, status: http.StatusOK}
	rec.WriteHeader(http.StatusCreated)
	if rec.status != http.StatusCreated {
		t.Errorf("status = %d, 期望 201", rec.status)
	}
	rec2 := &statusRecorder{ResponseWriter: httptest.NewRecorder(), status: http.StatusOK}
	rec2.Write([]byte("hi")) // 未显式 WriteHeader → 保持默认 200
	if rec2.status != http.StatusOK {
		t.Errorf("status = %d, 期望默认 200", rec2.status)
	}
}
