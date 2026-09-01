package main

import (
	"runtime"
	"strings"
	"testing"
	"time"
)

// waitGoroutines 轮询等待 goroutine 数量达到目标（调度有延迟，不能直接断言）
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

// TestLeakDetected 泄漏版：40 个发送方只消费一半（20 个结果）就返回，
// 其余 20 个发送 goroutine 永久阻塞在 ch <- work()——goroutine 数应显著增长，
// 且 goroutine profile 里能看到泄漏栈聚在 leakyFanOut
func TestLeakDetected(t *testing.T) {
	before := runtime.NumGoroutine()
	leakyFanOut(40, slowWork)
	after := waitGoroutines(t, func(n int) bool { return n >= before+20 }, "泄漏的 20 个发送 goroutine 就位")
	t.Logf("goroutine 数: %d -> %d（泄漏 20 个）", before, after)

	prof := goroutineProfile()
	if !strings.Contains(prof, "leakyFanOut") {
		t.Fatalf("goroutine profile 应包含泄漏发生的函数 leakyFanOut:\n%s", prof)
	}
	if !strings.Contains(prof, "main.go:29") { // ch <- work() 泄漏点所在行
		t.Fatalf("profile 应标出泄漏点行号（main.go:29）:\n%s", prof)
	}
}

// TestFixedNoLeak 修复版：缓冲 = 发送方数量，调用方只消费一半，发送方写完即退出——
// 前后两轮固定调用后 goroutine 数保持平稳（容忍测试框架自身的波动）
func TestFixedNoLeak(t *testing.T) {
	// 预热一轮，等环境稳定
	fixedFanOut(40, slowWork)
	time.Sleep(500 * time.Millisecond)
	before := runtime.NumGoroutine()

	for i := 0; i < 3; i++ {
		fixedFanOut(40, slowWork)
	}
	time.Sleep(500 * time.Millisecond)
	after := runtime.NumGoroutine()
	if after > before+2 {
		t.Fatalf("修复版仍泄漏: goroutine 数 %d -> %d", before, after)
	}
}

// TestBothCorrect 两版返回的已消费结果一致（泄漏的是发送方，不是结果）
func TestBothCorrect(t *testing.T) {
	if got := leakyFanOut(40, slowWork); got != 42*20 {
		t.Fatalf("leakyFanOut 结果=%d, want %d", got, 42*20)
	}
	if got := fixedFanOut(40, slowWork); got != 42*20 {
		t.Fatalf("fixedFanOut 结果=%d, want %d", got, 42*20)
	}
}
