package main

import (
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

// waitGoroutines 轮询等待 goroutine 数量达到目标（调度有时延，不能直接断言）
func waitGoroutines(t *testing.T, want func(n int) bool, what string) int {
	t.Helper()
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		n := runtime.NumGoroutine()
		if want(n) {
			return n
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatalf("等待 %s 超时，当前 goroutine 数=%d", what, runtime.NumGoroutine())
	return -1
}

// TestLeakDetected 泄漏版：20 次超时调用后 goroutine 数显著增长，且 profile 里能看到泄漏栈
func TestLeakDetected(t *testing.T) {
	before := runtime.NumGoroutine()
	for i := 0; i < 20; i++ {
		leakySend(slowWork, time.Millisecond)
	}
	after := waitGoroutines(t, func(n int) bool { return n >= before+20 }, "泄漏的 20 个 goroutine 就位")
	t.Logf("goroutine 数: %d -> %d（泄漏 20 个）", before, after)

	prof := goroutineProfile()
	if !strings.Contains(prof, "leakySend") {
		t.Fatalf("goroutine profile 应包含泄漏发生的函数 leakySend:\n%s", prof)
	}
}

// TestFixedNoLeak 修复版：超时放弃后 goroutine 数回落到基线（发送方写完缓冲即退出）
func TestFixedNoLeak(t *testing.T) {
	// 先等 TestLeakDetected 之外的环境稳定（本测试独立验证，不依赖上一个测试）
	for i := 0; i < 20; i++ {
		fixedSend(slowWork, time.Millisecond)
	}
	// 修复版的发送方在 50ms 内写完缓冲并退出；2 秒内 goroutine 数应停止增长
	time.Sleep(500 * time.Millisecond)
	before := runtime.NumGoroutine()
	for i := 0; i < 20; i++ {
		fixedSend(slowWork, time.Millisecond)
	}
	time.Sleep(500 * time.Millisecond)
	after := runtime.NumGoroutine()
	if after > before+2 { // 容忍测试框架自身的波动
		t.Fatalf("修复版仍泄漏: goroutine 数 %d -> %d", before, after)
	}
}

// TestCaptureTrace 验证 trace 文件真实生成且格式合法（magic header "go 1.25 trace"）
func TestCaptureTrace(t *testing.T) {
	path := filepath.Join(t.TempDir(), "trace.out")
	err := captureTrace(path, func() {
		for i := 0; i < 2; i++ {
			fixedSend(slowWork, time.Second)
		}
	})
	if err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(string(data), "go 1.25 trace") {
		t.Fatalf("trace 文件头不合法: %q", string(data[:min(20, len(data))]))
	}
	t.Logf("trace 文件 %d 字节，可用 go tool trace 打开（交互式 UI 未在本环境验证）", len(data))
}
