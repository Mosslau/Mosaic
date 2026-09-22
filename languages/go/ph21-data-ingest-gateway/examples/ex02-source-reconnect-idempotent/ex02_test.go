// 来源：ph21-data-ingest-gateway examples/ex02-agent-reconnect-idempotent/ex02_test.go
// 一句话说明：auth/dedup/平台 HTTP e2e/重连循环四组测试——token 时间窗与防伪、
// 幂等窗语义与有界性、HTTP 端到端（含 401 与重复拦截）、重连退避与鉴权失败短路。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"context"
	"errors"
	"net/http/httptest"
	"testing"
	"time"
)

// ---------- auth ----------

func TestTokenVerifyWithinWindow(t *testing.T) {
	now := time.Now()
	tok := SignToken("s3cr3t", "src-001", tokenSlotDur, now)
	if err := VerifyToken("s3cr3t", "src-001", tok, tokenSlotDur, now.Add(tokenSlotDur/2)); err != nil {
		t.Errorf("窗口内应通过: %v", err)
	}
}

func TestTokenRejectedWrongSecretAndAgent(t *testing.T) {
	now := time.Now()
	tok := SignToken("s3cr3t", "src-001", tokenSlotDur, now)
	if err := VerifyToken("wrong", "src-001", tok, tokenSlotDur, now); !errors.Is(err, ErrUnauthorized) {
		t.Errorf("错密钥应拒绝，got %v", err)
	}
	if err := VerifyToken("s3cr3t", "src-002", tok, tokenSlotDur, now); !errors.Is(err, ErrUnauthorized) {
		t.Errorf("错采集端应拒绝，got %v", err)
	}
}

func TestTokenExpiresAfterWindow(t *testing.T) {
	now := time.Now()
	tok := SignToken("s3cr3t", "src-001", tokenSlotDur, now)
	future := now.Add(tokenSlotDur * 3) // 离开当前槽与上一槽
	if err := VerifyToken("s3cr3t", "src-001", tok, tokenSlotDur, future); !errors.Is(err, ErrUnauthorized) {
		t.Errorf("过期 token 应拒绝，got %v", err)
	}
}

// ---------- deduper ----------

func TestDeduperSemantics(t *testing.T) {
	d := NewDeduper(3)
	cases := []struct {
		sourceID string
		seq      uint64
		want     bool
		why      string
	}{
		{"v1", 1, true, "首条"},
		{"v1", 2, true, "新 seq"},
		{"v1", 2, false, "窗口内重放（弱网重试）"},
		{"v1", 1, false, "乱序迟到（seq<=ceiling）"},
		{"v1", 3, true, "继续推进"},
	}
	for _, c := range cases {
		if got := d.FirstTime(c.sourceID, c.seq); got != c.want {
			t.Errorf("(%s,%d) = %v, want %v（%s）", c.sourceID, c.seq, got, c.want, c.why)
		}
	}
}

func TestDeduperBounded(t *testing.T) {
	d := NewDeduper(100)
	for i := 1; i <= 500; i++ {
		d.FirstTime("v1", uint64(i))
	}
	if d.Len() != 100 {
		t.Errorf("窗口应有界: Len=%d, want 100", d.Len())
	}
	// 被淘汰的最老条目（v1,1）再次出现：seqCeiling=500 的单调闸仍拦下它——
	// 内存窗负责"近窗去重"，单调闸负责"远窗旧 seq 一律拒绝"，两者互补。
	if d.FirstTime("v1", 1) {
		t.Error("窗口淘汰后的旧 seq 仍应被单调闸拦截")
	}
	// 新的大 seq 继续放行。
	if !d.FirstTime("v1", 501) {
		t.Error("窗口外新 seq 应放行")
	}
}

// ---------- platform e2e ----------

func TestPlatformHTTPEndToEnd(t *testing.T) {
	platform := NewPlatform(map[string]string{"src-001": "s3cr3t"})
	ts := httptest.NewServer(platform.Handler())
	defer ts.Close()

	dev := &Reporter{
		Endpoint: ts.URL + "/api/v1/metrics",
		AgentID:  "src-001", Secret: "s3cr3t",
		Client: ts.Client(),
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := dev.SendOnce(ctx, Metrics{SourceID: "src-001", Seq: 1, Value: 42}); err != nil {
		t.Fatalf("首次上报: %v", err)
	}
	// 同一 seq 重试：平台应判重复但 HTTP 仍 200（accepted=false），不报错。
	if err := dev.SendWithRetry(ctx, Metrics{SourceID: "src-001", Seq: 1, Value: 42}); err != nil {
		t.Fatalf("重试上报: %v", err)
	}
	if err := dev.SendOnce(ctx, Metrics{SourceID: "src-001", Seq: 2, Value: 43}); err != nil {
		t.Fatalf("第二条: %v", err)
	}

	ingest, dup, _ := platform.Stats()
	if ingest != 2 {
		t.Errorf("生效应 2 条, got %d", ingest)
	}
	if dup != 1 {
		t.Errorf("重复拦截应 1 条, got %d", dup)
	}

	// 坏 token：SendOnce 应返回 ErrUnauthorized。
	bad := &Reporter{
		Endpoint: ts.URL + "/api/v1/metrics",
		AgentID:  "src-001", Secret: "wrong",
		Client: ts.Client(),
	}
	err := bad.SendOnce(ctx, Metrics{SourceID: "src-001", Seq: 3, Value: 0})
	if !errors.Is(err, ErrUnauthorized) {
		t.Errorf("坏 token 应 ErrUnauthorized, got %v", err)
	}
	if _, _, auth := platform.Stats(); auth != 1 {
		t.Errorf("鉴权失败计数应 1, got %d", auth)
	}
}

// ---------- reconnect loop ----------

func TestReconnectRetriesTransientThenSucceeds(t *testing.T) {
	attempts := 0
	var sleeps []time.Duration
	loop := &ReconnectLoop{
		Try: func() error {
			attempts++
			if attempts < 3 {
				return errors.New("模拟网络瞬断")
			}
			return nil
		},
		BaseBackoff: 10 * time.Millisecond,
		MaxBackoff:  40 * time.Millisecond,
		MaxAttempts: 5,
		Jitter:      func() int64 { return 0 }, // 无抖动，退避序列可精确断言
		Sleep: func(_ context.Context, d time.Duration) error {
			sleeps = append(sleeps, d)
			return nil
		},
	}
	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("应重试成功: %v", err)
	}
	if attempts != 3 {
		t.Errorf("应尝试 3 次, got %d", attempts)
	}
	want := []time.Duration{10 * time.Millisecond, 20 * time.Millisecond}
	if len(sleeps) != 2 || sleeps[0] != want[0] || sleeps[1] != want[1] {
		t.Errorf("退避序列应为 10ms,20ms, got %v", sleeps)
	}
}

func TestReconnectStopsOnUnauthorized(t *testing.T) {
	attempts := 0
	loop := &ReconnectLoop{
		Try: func() error {
			attempts++
			return ErrUnauthorized
		},
		BaseBackoff: time.Second, MaxBackoff: time.Second, MaxAttempts: 9,
		Sleep: func(context.Context, time.Duration) error { return nil },
	}
	err := loop.Run(context.Background())
	if !errors.Is(err, ErrUnauthorized) {
		t.Fatalf("应返回 ErrUnauthorized, got %v", err)
	}
	if attempts != 1 {
		t.Errorf("鉴权失败不应重试, attempts=%d", attempts)
	}
}

func TestReconnectGivesUpAfterMaxAttempts(t *testing.T) {
	attempts := 0
	loop := &ReconnectLoop{
		Try:         func() error { attempts++; return errors.New("持续断网") },
		BaseBackoff: time.Millisecond, MaxBackoff: 2 * time.Millisecond, MaxAttempts: 4,
		Sleep: func(context.Context, time.Duration) error { return nil },
	}
	if err := loop.Run(context.Background()); err == nil {
		t.Fatal("耗尽次数应报错")
	}
	if attempts != 4 {
		t.Errorf("应恰好尝试 4 次, got %d", attempts)
	}
}
