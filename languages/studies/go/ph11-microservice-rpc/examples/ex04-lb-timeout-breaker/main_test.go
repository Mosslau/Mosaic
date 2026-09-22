package main

import (
	"errors"
	"strings"
	"testing"
	"time"
)

// ---- 负载均衡 ----

func TestRoundRobinSequence(t *testing.T) {
	rr := NewRoundRobin([]string{"A", "B", "C"})
	want := []string{"A", "B", "C", "A", "B", "C"}
	for i, w := range want {
		if got := rr.Pick(); got != w {
			t.Fatalf("pick#%d = %q, want %q", i+1, got, w)
		}
	}
}

func TestRoundRobinEmpty(t *testing.T) {
	rr := NewRoundRobin(nil)
	if got := rr.Pick(); got != "" {
		t.Fatalf("空列表 Pick 应为空串, got %q", got)
	}
}

// ---- 超时 ----

func TestCallWithTimeoutOK(t *testing.T) {
	err := callWithTimeout(200*time.Millisecond, func() error { return nil })
	if err != nil {
		t.Fatalf("快速函数不应超时: %v", err)
	}
}

func TestCallWithTimeoutFires(t *testing.T) {
	start := time.Now()
	err := callWithTimeout(50*time.Millisecond, func() error {
		time.Sleep(500 * time.Millisecond) // 慢于超时
		return nil
	})
	if !errors.Is(err, ErrTimeout) {
		t.Fatalf("应返回 ErrTimeout, got %v", err)
	}
	if time.Since(start) > 300*time.Millisecond {
		t.Fatalf("超时应在 ~50ms 触发, 实际 %v", time.Since(start))
	}
}

func TestCallWithTimeoutErrorPropagates(t *testing.T) {
	sentinel := errors.New("boom")
	err := callWithTimeout(200*time.Millisecond, func() error { return sentinel })
	if !errors.Is(err, sentinel) {
		t.Fatalf("函数错误应透传, got %v", err)
	}
}

// ---- 熔断状态机 ----

func TestBreakerOpensAfterThreshold(t *testing.T) {
	b := NewBreaker(2, time.Hour) // 冷却极长：保证不自动半开
	if b.State() != "closed" {
		t.Fatalf("初始应为 closed, got %s", b.State())
	}
	if !b.Allow() {
		t.Fatal("closed 应放行")
	}
	b.Failure()
	if b.State() != "closed" {
		t.Fatal("1 次失败未达阈值, 应仍 closed")
	}
	b.Failure() // 第 2 次失败 → 打开
	if b.State() != "open" {
		t.Fatalf("达阈值应 open, got %s", b.State())
	}
	if b.Allow() {
		t.Fatal("open 冷却期应拒绝放行（快速失败）")
	}
}

func TestBreakerHalfOpenSuccessCloses(t *testing.T) {
	b := NewBreaker(1, 50*time.Millisecond)
	b.Failure() // 打开
	if b.State() != "open" {
		t.Fatal("应已 open")
	}
	time.Sleep(80 * time.Millisecond) // 过冷却期
	if !b.Allow() {
		t.Fatal("冷却后应半开放行探针")
	}
	if b.State() != "half-open" {
		t.Fatalf("放行后应 half-open, got %s", b.State())
	}
	b.Success() // 探针成功 → 复位 closed
	if b.State() != "closed" {
		t.Fatalf("探针成功后应 closed, got %s", b.State())
	}
	if !b.Allow() {
		t.Fatal("closed 应正常放行")
	}
}

func TestBreakerHalfOpenFailureReopens(t *testing.T) {
	b := NewBreaker(1, 50*time.Millisecond)
	b.Failure()
	time.Sleep(80 * time.Millisecond)
	if !b.Allow() { // 半开放行探针
		t.Fatal("冷却后应放行")
	}
	b.Failure() // 探针失败 → 回到 open
	if b.State() != "open" {
		t.Fatalf("探针失败应回到 open, got %s", b.State())
	}
	if b.Allow() {
		t.Fatal("重新 open 后应拒绝")
	}
}

func TestBreakerSuccessResetsCounter(t *testing.T) {
	b := NewBreaker(3, time.Hour)
	b.Failure()
	b.Failure()
	b.Success() // 中途成功 → 计数清零
	b.Failure()
	if b.State() != "closed" {
		t.Fatalf("清零后 1 次失败不应打开, got %s", b.State())
	}
}

// ---- 集成：真实 RPC 实例 + 熔断 ----

func TestCallInstanceIntegration(t *testing.T) {
	fastAddr, stopFast, err := startServer("fast")
	if err != nil {
		t.Fatal(err)
	}
	defer stopFast()

	b := NewBreaker(2, 100*time.Millisecond)
	from, err := callInstance(fastAddr, b, 200*time.Millisecond, 7)
	if err != nil {
		t.Fatalf("fast 调用应成功: %v", err)
	}
	if from != "fast" {
		t.Fatalf("from=%q, want fast", from)
	}
	if b.State() != "closed" {
		t.Fatalf("成功应保持 closed, got %s", b.State())
	}
}

func TestCallInstanceSlowTimesOut(t *testing.T) {
	slowAddr, stopSlow, err := startServer("slow")
	if err != nil {
		t.Fatal(err)
	}
	defer stopSlow()

	b := NewBreaker(2, 100*time.Millisecond)
	start := time.Now()
	_, err = callInstance(slowAddr, b, 100*time.Millisecond, 1)
	if !errors.Is(err, ErrTimeout) {
		t.Fatalf("慢实例应超时: %v", err)
	}
	if time.Since(start) > 500*time.Millisecond {
		t.Fatalf("超时触发过慢: %v", time.Since(start))
	}
	if b.State() != "closed" { // 1 次失败未达阈值
		t.Fatalf("1 次超时不应打开, got %s", b.State())
	}
}

func TestCallInstanceBreakerOpens(t *testing.T) {
	failAddr, stopFail, err := startServer("fail")
	if err != nil {
		t.Fatal(err)
	}
	defer stopFail()

	b := NewBreaker(2, time.Hour) // 冷却极长，锁定 open
	if _, err := callInstance(failAddr, b, 200*time.Millisecond, 1); err == nil {
		t.Fatal("故障实例应报错")
	}
	if _, err := callInstance(failAddr, b, 200*time.Millisecond, 2); err == nil {
		t.Fatal("故障实例应报错")
	}
	if b.State() != "open" {
		t.Fatalf("连续失败应打开, got %s", b.State())
	}
	// 打开后：快速失败，不发起网络调用（错误信息带"熔断开启"）
	_, err = callInstance(failAddr, b, 200*time.Millisecond, 3)
	if err == nil || !strings.Contains(err.Error(), "熔断开启") {
		t.Fatalf("打开后应快速失败, got %v", err)
	}
}
