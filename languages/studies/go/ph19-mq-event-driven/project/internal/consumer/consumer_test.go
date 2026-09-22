// 来源：ph19-mq-event-driven project/internal/consumer/consumer_test.go
// 一句话说明：消费循环的单元测试（替身 Log/Processor）——幂等拦截重复投递、
// 解码毒消息、schema 毒消息、重试耗尽死信、重试后成功。e2e 见项目根目录。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package consumer

import (
	"errors"
	"testing"

	"tenetlang/go/ph19-mq-event-driven/project/internal/model"
	"tenetlang/go/ph19-mq-event-driven/project/internal/process"
	"tenetlang/go/ph19-mq-event-driven/project/internal/store"
)

// stubLog 测试替身：实现 Log（内部包可直接构造）。
type stubLog struct {
	numParts int
	parts    map[int][]model.Message // 只含一条分区供测试
}

func (s *stubLog) NumPartitions() int { return s.numParts }
func (s *stubLog) HighWater(p int) int {
	if p >= s.numParts {
		return 0
	}
	if recs, ok := s.parts[p]; ok {
		return len(recs)
	}
	return 0
}
func (s *stubLog) Slice(p, from int) []model.Message {
	recs := s.parts[p]
	if from > len(recs) {
		from = len(recs)
	}
	return append([]model.Message(nil), recs[from:]...)
}

// seqProc 可编程 Processor：按调用次数返回错误。
type seqProc struct {
	calls int
	// fail 策略：每次返回该错误直到 maxCalls 后返回 nil；err 为 nil 表示永不失败。
	err      error
	maxCalls int
}

func (p *seqProc) Process(model.Message) error {
	p.calls++
	if p.err == nil {
		return nil
	}
	if p.maxCalls > 0 && p.calls >= p.maxCalls {
		return nil
	}
	return p.err
}

func mustEncode(e model.TelemetryEvent) []byte {
	b, err := e.Encode()
	if err != nil {
		panic(err)
	}
	return b
}

func newStub(msgs []model.Message) *stubLog {
	return &stubLog{numParts: 1, parts: map[int][]model.Message{0: msgs}}
}

// TestDuplicateDeliverySkipped 重复投递（同 MsgID 两次出现）：生效一次，拦截一次。
func TestDuplicateDeliverySkipped(t *testing.T) {
	ev := model.TelemetryEvent{MsgID: "m1", SchemaVersion: 1, VehicleID: "car-1", TS: 1, Speed: 10}
	log := newStub([]model.Message{
		{Partition: 0, Offset: 0, Payload: mustEncode(ev)},
		{Partition: 0, Offset: 1, Payload: mustEncode(ev)},
	})
	c := New(log, store.NewSeenWindow(100), &seqProc{}, store.NewDeadLog(), Config{MaxAttempts: 3})
	rep := c.RunOnce()
	if rep.Applied != 1 || rep.DuplicateSkipped != 1 {
		t.Fatalf("report=%+v, want applied=1 dup=1", rep)
	}
}

// TestPoisonDecode 坏载荷：直接死信（decode 分类），不重试。
func TestPoisonDecode(t *testing.T) {
	log := newStub([]model.Message{{Partition: 0, Offset: 0, Payload: []byte("not-json")}})
	dlog := store.NewDeadLog()
	c := New(log, store.NewSeenWindow(100), &seqProc{}, dlog, Config{MaxAttempts: 3})
	rep := c.RunOnce()
	if rep.Poisoned != 1 || rep.Consumed != 1 {
		t.Fatalf("report=%+v", rep)
	}
	if dlog.Entries()[0].Reason != "decode" {
		t.Fatalf("reason=%q, want decode", dlog.Entries()[0].Reason)
	}
}

// TestPoisonSchema 未来 schema 版本：Processor 返回 ErrSchema → 死信 schema 分类。
func TestPoisonSchema(t *testing.T) {
	ev := model.TelemetryEvent{MsgID: "m9", SchemaVersion: 9, VehicleID: "car-9"}
	log := newStub([]model.Message{{Partition: 0, Offset: 0, Payload: mustEncode(ev)}})
	dlog := store.NewDeadLog()
	c := New(log, store.NewSeenWindow(100), &seqProc{err: process.ErrSchema}, dlog, Config{MaxAttempts: 3})
	rep := c.RunOnce()
	if rep.Poisoned != 1 {
		t.Fatalf("report=%+v", rep)
	}
	if dlog.Entries()[0].Reason != "schema" {
		t.Fatalf("reason=%q, want schema", dlog.Entries()[0].Reason)
	}
}

// TestRetryThenSuccess 抖动恢复：失败一次后成功 → applied=1、retried=1、无死信。
func TestRetryThenSuccess(t *testing.T) {
	ev := model.TelemetryEvent{MsgID: "m2", SchemaVersion: 1, VehicleID: "car-2"}
	log := newStub([]model.Message{{Partition: 0, Offset: 0, Payload: mustEncode(ev)}})
	c := New(log, store.NewSeenWindow(100),
		&seqProc{err: errors.New("downstream down"), maxCalls: 2},
		store.NewDeadLog(), Config{MaxAttempts: 3})
	rep := c.RunOnce()
	if rep.Applied != 1 || rep.Retried != 1 || rep.Poisoned+rep.Exhausted != 0 {
		t.Fatalf("report=%+v", rep)
	}
}

// TestExhaustedAfterRetries 持续瞬时故障：达到上限进死信（exhausted）。
func TestExhaustedAfterRetries(t *testing.T) {
	ev := model.TelemetryEvent{MsgID: "m3", SchemaVersion: 1, VehicleID: "car-3"}
	log := newStub([]model.Message{{Partition: 0, Offset: 0, Payload: mustEncode(ev)}})
	dlog := store.NewDeadLog()
	c := New(log, store.NewSeenWindow(100),
		&seqProc{err: errors.New("always down")},
		dlog, Config{MaxAttempts: 3})
	rep := c.RunOnce()
	if rep.Exhausted != 1 || rep.Retried != 2 {
		t.Fatalf("report=%+v, want exhausted=1 retried=2", rep)
	}
	if e := dlog.Entries()[0]; e.Reason != "exhausted" || e.Attempts != 3 {
		t.Fatalf("dead entry=%+v", e)
	}
}
