// 来源：ph19-mq-event-driven exercises/sol-03-idempotent-consumer（练习 3 参考实现）
// 一句话说明：练习 3 验收的可执行版本——窗口内去重、过期后可再消费、并发重复
// 投递只生效一次、失败回滚预约、注入时钟驱动边界（主文档 3.5）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"errors"
	"sync"
	"testing"
	"time"
)

const testTTL = 10 * time.Minute

func newTestConsumer(sink Sink, now *time.Time) *IdempotentConsumer {
	d := NewDedupeWindow(testTTL, 1000)
	c := NewIdempotentConsumer(d, sink)
	c.now = func() time.Time { return *now }
	return c
}

func ev(id string) DeviceEvent {
	return DeviceEvent{MsgID: id, CarID: "car-001", Kind: "telemetry", Data: "x"}
}

// TestDedupWithinWindow 窗口内重复键被拦截，副作用只一次。
func TestDedupWithinWindow(t *testing.T) {
	now := time.Unix(0, 0)
	c := newTestConsumer(&DuplicateCounterSink{}, &now)
	sink := c.sink.(*DuplicateCounterSink)

	applied, err := c.Consume(ev("m1"))
	if err != nil || !applied {
		t.Fatalf("first consume applied=%v err=%v", applied, err)
	}
	now = now.Add(time.Minute) // 仍 < TTL
	applied, err = c.Consume(ev("m1"))
	if err != nil || applied {
		t.Fatalf("duplicate should be skipped, applied=%v err=%v", applied, err)
	}
	if sink.Count() != 1 {
		t.Fatalf("effect count=%d, want 1", sink.Count())
	}
}

// TestExpiredKeyAllowedAgain 过期后同键可以再次生效（窗口不是永久黑名单）。
func TestExpiredKeyAllowedAgain(t *testing.T) {
	now := time.Unix(0, 0)
	c := newTestConsumer(&DuplicateCounterSink{}, &now)
	sink := c.sink.(*DuplicateCounterSink)

	c.Consume(ev("m1"))
	now = now.Add(2 * testTTL) // 超窗
	applied, err := c.Consume(ev("m1"))
	if err != nil || !applied {
		t.Fatalf("expired key should apply again, applied=%v err=%v", applied, err)
	}
	if sink.Count() != 2 {
		t.Fatalf("effect count=%d, want 2", sink.Count())
	}
}

// TestConcurrentDuplicateAppliesOnce 并发重复投递：CheckAndMark 原子 → 只生效一次。
func TestConcurrentDuplicateAppliesOnce(t *testing.T) {
	now := time.Unix(0, 0)
	c := newTestConsumer(&DuplicateCounterSink{}, &now)
	sink := c.sink.(*DuplicateCounterSink)

	const n = 8
	var wg sync.WaitGroup
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, _ = c.Consume(ev("m-race")) // 8 个 goroutine 同时投同一条
		}()
	}
	wg.Wait()
	if sink.Count() != 1 {
		t.Fatalf("effect count=%d, want 1（原子查重+记账必须拦下并发重复）", sink.Count())
	}
}

// flakyOnceSink 第一次 Apply 失败（模拟下游抖动），之后成功并记录。
type flakyOnceSink struct {
	fail    bool
	applied []DeviceEvent
}

func (s *flakyOnceSink) Apply(e DeviceEvent) error {
	if s.fail {
		s.fail = false
		return errors.New("downstream down")
	}
	s.applied = append(s.applied, e)
	return nil
}

func (s *flakyOnceSink) Count() int { return len(s.applied) }

// TestFailRollsBackReservation 副作用失败回滚预约：重投可以重试成功。
func TestFailRollsBackReservation(t *testing.T) {
	now := time.Unix(0, 0)
	d := NewDedupeWindow(testTTL, 100)
	sink := &flakyOnceSink{fail: true}
	c := NewIdempotentConsumer(d, sink)
	c.now = func() time.Time { return now }

	// 第一次：副作用失败 → 预约回滚
	applied, err := c.Consume(ev("m1"))
	if applied || err == nil {
		t.Fatalf("first attempt should fail, applied=%v", applied)
	}
	// 第二次（模拟消息被重投）：预约已回滚 → 可再次尝试并成功
	applied, err = c.Consume(ev("m1"))
	if err != nil || !applied {
		t.Fatalf("retry after rollback should succeed, applied=%v err=%v", applied, err)
	}
	if sink.Count() != 1 {
		t.Fatalf("effect count=%d, want 1", sink.Count())
	}
}
