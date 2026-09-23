// 来源：ph19-mq-event-driven exercises/sol-03-idempotent-consumer（练习 3 参考实现）
// 一句话说明：基于"时间窗"的幂等消费——去重键在 TTL 内只放行一次，过期键可再消费。
// 与 examples/ex02 的容量 FIFO 去重互补：窗口语义适合"重试/重复投递集中在短时间内"
// 的生产场景，代价是内存需定期剪除过期键。并发安全：CheckAndMark 在锁内原子完成
// "查重+记账"，并发重复投递也只生效一次（真实工程可换 Redis SETNX + TTL，语义相同）。
// 真 broker 切换：本模块的输入流换成 kafka-go/NATS 的消费循环后，去重层不用改——
// 把 sink.Apply 接在你的业务副作用上即可。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"fmt"
	"sync"
	"time"
)

// DeviceEvent 设备事件（MsgID 是幂等键，producer 保证唯一、重投不变）。
type DeviceEvent struct {
	MsgID string
	CarID string
	Kind  string // e.g. telemetry / alarm
	Data  string
}

// DedupeWindow 时间窗去重表：map[id]首次记账时间，TTL 内重复键被拦截。
// max 限制最大记忆数：超限时先剪除已过期键（懒剪除，均摊 O(1)）。
type DedupeWindow struct {
	mu     sync.Mutex
	ttl    time.Duration
	max    int
	seenAt map[string]time.Time
}

// NewDedupeWindow 建窗口；ttl<=0 视为永不过期（谨慎：会无限膨胀）。
func NewDedupeWindow(ttl time.Duration, max int) *DedupeWindow {
	if ttl <= 0 {
		ttl = 365 * 24 * time.Hour
	}
	return &DedupeWindow{ttl: ttl, max: max, seenAt: make(map[string]time.Time)}
}

// CheckAndMark 查重并记账（原子）：返回 true 表示"窗口内已见过，本次应跳过"。
// now 由调用方传入，便于测试注入时钟（golang-patterns：可注入使单测不依赖真时间）。
func (d *DedupeWindow) CheckAndMark(id string, now time.Time) bool {
	d.mu.Lock()
	defer d.mu.Unlock()
	if at, ok := d.seenAt[id]; ok && now.Sub(at) < d.ttl {
		return true // 窗口内重复：拒绝
	}
	d.seenAt[id] = now
	if len(d.seenAt) > d.max {
		d.purgeLocked(now)
	}
	return false
}

// Forget 撤销一次记账（副作用失败时回滚预约）。
func (d *DedupeWindow) Forget(id string) {
	d.mu.Lock()
	defer d.mu.Unlock()
	delete(d.seenAt, id)
}

// purgeLocked 剪除已过期键（调用方已持锁）。map 超限才会触发，摊还成本低。
func (d *DedupeWindow) purgeLocked(now time.Time) {
	for id, at := range d.seenAt {
		if now.Sub(at) >= d.ttl {
			delete(d.seenAt, id)
		}
	}
	// 剪完仍超限：删最旧的（上限保险丝，避免 max 设置过小的极端场景）。
	for len(d.seenAt) > d.max {
		var oldestID string
		var oldest time.Time
		for id, at := range d.seenAt {
			if oldestID == "" || at.Before(oldest) {
				oldestID, oldest = id, at
			}
		}
		delete(d.seenAt, oldestID)
	}
}

// Sink 副作用出口：真实工程是 DB/下游，这里只要求"对一个事件生效一次"。
type Sink interface {
	Apply(e DeviceEvent) error
}

// IdempotentConsumer 幂等消费循环：去重层包在业务外层，业务自身不再关心重复。
type IdempotentConsumer struct {
	dedup *DedupeWindow
	sink  Sink
	now   func() time.Time // 可注入时钟
}

// NewIdempotentConsumer 构造消费者。
func NewIdempotentConsumer(dedup *DedupeWindow, sink Sink) *IdempotentConsumer {
	return &IdempotentConsumer{dedup: dedup, sink: sink, now: time.Now}
}

// Consume 消费一条事件：窗口内重复→跳过；否则执行副作用。
// 顺序：先 CheckAndMark（预约）再 Apply；Apply 失败回滚预约（Forget），
// 让重投有机会重试。诚实边界：预约与生效之间进程崩溃仍可能丢消息或重放，
// 真正的 exactly-once 需要 outbox/事务把"记账与副作用"做成原子（主文档 3.9）。
func (c *IdempotentConsumer) Consume(e DeviceEvent) (applied bool, err error) {
	now := c.now()
	if c.dedup.CheckAndMark(e.MsgID, now) {
		return false, nil // 窗口内重复投递：跳过副作用
	}
	if err := c.sink.Apply(e); err != nil {
		c.dedup.Forget(e.MsgID) // 回滚预约：失败要能被重投重试
		return false, fmt.Errorf("apply %s: %w", e.MsgID, err)
	}
	return true, nil
}

// DuplicateCounterSink 演示用副作用 sink：只统计首次生效的事件。
type DuplicateCounterSink struct {
	mu      sync.Mutex
	applied []DeviceEvent
}

// Apply 记录事件（演示副作用：append 到列表）。
func (s *DuplicateCounterSink) Apply(e DeviceEvent) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.applied = append(s.applied, e)
	return nil
}

// Count 已生效事件数。
func (s *DuplicateCounterSink) Count() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.applied)
}
