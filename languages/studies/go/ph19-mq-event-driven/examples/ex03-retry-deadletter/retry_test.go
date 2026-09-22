// 来源：ph19-mq-event-driven examples/ex03-retry-deadletter/retry_test.go
// 一句话说明：重试/死信状态机的可执行断言——成功路径、失败后重试成功、
// 次数耗尽进死信、毒消息不重试立即进死信、退避时长单调递增。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"errors"
	"fmt"
	"strings"
	"testing"
	"time"
)

// noopSleep 测试里把真 sleep 换成空实现，让重试状态机瞬间跑完。
func noopSleep(time.Duration) {}

// newTestPipeline 构造干净流水线并记录每次请求的退避时长（便于断言递增）。
func newTestPipeline(max int) (*Pipeline, *DLQ, *[]time.Duration) {
	dlq := NewDLQ()
	var waits []time.Duration
	p := NewPipeline(Config{
		MaxAttempts: max,
		Backoff: func(n int) time.Duration {
			d := time.Duration(n) * 10 * time.Millisecond
			waits = append(waits, d) // 只记账，不真等
			return d
		},
		sleep: noopSleep,
	}, dlq)
	return p, dlq, &waits
}

// TestSuccessFirstTry 一次成功：0 次重试、无退避、不进死信。
func TestSuccessFirstTry(t *testing.T) {
	p, dlq, waits := newTestPipeline(3)
	out := p.Handle(Message{ID: "m1", Payload: "p"}, func(Message) error { return nil })
	if out.Status != StatusDone || out.Attempts != 1 {
		t.Fatalf("got status=%v attempts=%d, want done/1", out.Status, out.Attempts)
	}
	if len(*waits) != 0 {
		t.Fatalf("backoff called %d times on first-try success", len(*waits))
	}
	if dlq.Len() != 0 {
		t.Fatal("no dead letter expected")
	}
}

// TestRetryThenSuccess 前两次失败、第三次成功：重试 2 次、退避 2 次、最终 done。
func TestRetryThenSuccess(t *testing.T) {
	p, dlq, waits := newTestPipeline(5)
	attempts := 0
	out := p.Handle(Message{ID: "m1", Payload: "p"}, func(Message) error {
		attempts++
		if attempts < 3 {
			return Retryable(errors.New("boom"))
		}
		return nil
	})
	if out.Status != StatusDone || out.Attempts != 3 {
		t.Fatalf("got status=%v attempts=%d, want done/3", out.Status, out.Attempts)
	}
	if len(*waits) != 2 {
		t.Fatalf("backoff count=%d, want 2", len(*waits))
	}
	if dlq.Len() != 0 {
		t.Fatal("no dead letter expected")
	}
}

// TestExhaustedGoesToDLQ 永远可重试失败：打满 MaxAttempts 后进死信，附死因。
func TestExhaustedGoesToDLQ(t *testing.T) {
	p, dlq, _ := newTestPipeline(3)
	out := p.Handle(Message{ID: "m2", Payload: "p"}, func(Message) error {
		return Retryable(errors.New("downstream down"))
	})
	if out.Status != StatusDead || out.Attempts != 3 {
		t.Fatalf("got status=%v attempts=%d, want dead/3", out.Status, out.Attempts)
	}
	if dlq.Len() != 1 {
		t.Fatalf("dlq.Len=%d, want 1", dlq.Len())
	}
	e := dlq.Entries()[0]
	if e.Message.ID != "m2" || e.Attempts != 3 {
		t.Fatalf("entry=%+v", e)
	}
	if !strings.Contains(e.Reason, "重试 2 次仍失败") {
		t.Fatalf("reason=%q should mention retries exhausted", e.Reason)
	}
}

// TestPoisonSkipsRetries 毒消息：只调用 1 次处理（不重试）即进死信，即使配额更多。
func TestPoisonSkipsRetries(t *testing.T) {
	p, dlq, waits := newTestPipeline(6)
	calls := 0
	out := p.Handle(Message{ID: "m3", Payload: "bad"}, func(Message) error {
		calls++
		return fmt.Errorf("%w: cannot decode", ErrPoison)
	})
	if out.Status != StatusDead {
		t.Fatalf("status=%v, want dead", out.Status)
	}
	if calls != 1 {
		t.Fatalf("handler calls=%d, want 1（毒消息不重试）", calls)
	}
	if len(*waits) != 0 {
		t.Fatalf("backoff count=%d, want 0", len(*waits))
	}
	if dlq.Len() != 1 {
		t.Fatalf("dlq.Len=%d, want 1", dlq.Len())
	}
	if reason := dlq.Entries()[0].Reason; !strings.Contains(reason, "毒消息") {
		t.Fatalf("reason=%q should mention 毒消息", reason)
	}
}

// TestRetryableErrorChain 包装链完整：Retryable 包底层错误，errors.Is 直达底层。
func TestRetryableErrorChain(t *testing.T) {
	cause := errors.New("io timeout")
	err := Retryable(cause)
	if !errors.Is(err, cause) {
		t.Fatal("errors.Is should reach wrapped cause")
	}
	if errors.Is(err, ErrPoison) {
		t.Fatal("retryable must not be poison")
	}
}

// TestBackoffIncreasing 退避单调递增：第 2 次重试前等得比第 1 次久（指数/线性设计）。
func TestBackoffIncreasing(t *testing.T) {
	p, _, waits := newTestPipeline(5)
	_ = p.Handle(Message{ID: "m1", Payload: "p"}, func(Message) error {
		return Retryable(errors.New("flaky"))
	})
	if len(*waits) < 2 {
		t.Fatalf("backoff recorded %d times, want >=2", len(*waits))
	}
	for i := 1; i < len(*waits); i++ {
		if (*waits)[i] <= (*waits)[i-1] {
			t.Fatalf("backoff not increasing: %v", *waits)
		}
	}
}
