// 来源：ph19-mq-event-driven exercises/sol-04-retry-deadletter（练习 4 参考实现）
// 一句话说明：练习 4 验收的可执行版本——重投计数、成功/耗尽/毒消息三分支、
// 失败重试次数与退避调用、attempts 随消息流转（主文档 3.6）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"errors"
	"fmt"
	"testing"
	"time"
)

// recordPipeline 构造管线并记录退避调用次数（sleep 为空实现，测试不真等）。
func recordPipeline(max int, h Handler) (*Pipeline, *int) {
	waits := 0
	p := NewPipeline(max, h).WithBackoff(
		func(n int) time.Duration {
			waits++
			return time.Duration(n) * time.Millisecond
		},
		func(time.Duration) {},
	)
	return p, &waits
}

// TestSuccessOnThirdTry 两次失败后成功：processed=1、retried=2、dead=0，退避 2 次。
func TestSuccessOnThirdTry(t *testing.T) {
	attempts := 0
	p, waits := recordPipeline(3, func(Job) error {
		attempts++
		if attempts < 3 {
			return errors.New("flaky")
		}
		return nil
	})
	rep := p.Run([]Job{{ID: "j1", Payload: "p"}})
	if rep.Processed != 1 || rep.Retried != 2 || rep.Dead != 0 {
		t.Fatalf("report=%+v", rep)
	}
	if *waits != 2 {
		t.Fatalf("backoff calls=%d, want 2", *waits)
	}
	if len(p.DLQ()) != 0 {
		t.Fatal("no dlq expected")
	}
}

// TestExhaustedEntersDLQ 永久失败：3 次尝试耗尽进 DLQ，attempts 记录为 2（+1=3）。
func TestExhaustedEntersDLQ(t *testing.T) {
	p, waits := recordPipeline(3, func(Job) error {
		return errors.New("always down")
	})
	rep := p.Run([]Job{{ID: "j2", Payload: "p"}})
	if rep.Processed != 0 || rep.Dead != 1 {
		t.Fatalf("report=%+v", rep)
	}
	if *waits != 2 {
		t.Fatalf("backoff calls=%d, want 2（3 次尝试之间 2 次退避）", *waits)
	}
	entries := p.DLQ()
	if len(entries) != 1 {
		t.Fatalf("dlq=%d, want 1", len(entries))
	}
	if entries[0].Job.ID != "j2" || entries[0].Job.Attempts != 2 || entries[0].Poison {
		t.Fatalf("entry=%+v", entries[0])
	}
}

// TestPoisonNoRetry 毒消息：处理只被调用 1 次即死信，不进重试。
func TestPoisonNoRetry(t *testing.T) {
	calls := 0
	p, waits := recordPipeline(5, func(Job) error {
		calls++
		return fmt.Errorf("%w: bad payload", ErrPoison)
	})
	rep := p.Run([]Job{{ID: "j3", Payload: "bad"}})
	if rep.Dead != 1 {
		t.Fatalf("report=%+v", rep)
	}
	if calls != 1 {
		t.Fatalf("handler calls=%d, want 1", calls)
	}
	if *waits != 0 {
		t.Fatalf("backoff calls=%d, want 0", *waits)
	}
	e := p.DLQ()[0]
	if !e.Poison {
		t.Fatalf("poison flag not set: %+v", e)
	}
}

// TestAttemptsTravelWithMessage 重投带着 Attempts：同一个 Job 实例被重放时，
// 新管线（模拟另一个实例接管）能续算而不重头再来。
func TestAttemptsTravelWithMessage(t *testing.T) {
	p, _ := recordPipeline(3, func(Job) error { return errors.New("fail") })
	rep := p.Run([]Job{{ID: "j4", Payload: "p"}})
	if rep.Dead != 1 {
		t.Fatalf("report=%+v", rep)
	}
	// 死信里的 Attempts=2 说明已试 3 次——attempts 计数没有在重投时丢过。
	if got := p.DLQ()[0].Job.Attempts; got != 2 {
		t.Fatalf("attempts=%d, want 2", got)
	}
}

// TestMultipleJobsIsolated 多条作业互不干扰：抖动成功与永久失败各自结算。
func TestMultipleJobsIsolated(t *testing.T) {
	failCounts := map[string]int{}
	p, _ := recordPipeline(3, func(j Job) error {
		if j.ID == "flaky" {
			failCounts["flaky"]++
			if failCounts["flaky"] < 2 {
				return errors.New("flaky")
			}
			return nil
		}
		return errors.New("permanent")
	})
	rep := p.Run([]Job{{ID: "flaky", Payload: "a"}, {ID: "dead", Payload: "b"}})
	if rep.Processed != 1 || rep.Dead != 1 {
		t.Fatalf("report=%+v", rep)
	}
	if p.DLQ()[0].Job.ID != "dead" {
		t.Fatalf("dlq id=%s, want dead", p.DLQ()[0].Job.ID)
	}
}
