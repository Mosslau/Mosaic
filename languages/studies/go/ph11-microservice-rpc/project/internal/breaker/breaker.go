// Package breaker 熔断器——closed → open → half-open 状态机的实现。
// 概念见阶段笔记 3.5/4.3：连续失败达阈值 → open（快速失败，不发网络调用给下游喘息）；
// 冷却期后 half-open 放行一个探针：成功复位 closed，失败回到 open。防雪崩连锁。
package breaker

import (
	"sync"
	"time"
)

// Breaker 熔断器
type Breaker struct {
	mu        sync.Mutex
	state     string // "closed" | "open" | "half-open"
	failures  int
	threshold int
	cooldown  time.Duration
	openedAt  time.Time
}

func New(threshold int, cooldown time.Duration) *Breaker {
	return &Breaker{state: "closed", threshold: threshold, cooldown: cooldown}
}

// Allow 是否放行本次调用；open 冷却中拒绝（快速失败）
func (b *Breaker) Allow() bool {
	b.mu.Lock()
	defer b.mu.Unlock()
	switch b.state {
	case "open":
		if time.Since(b.openedAt) > b.cooldown {
			b.state = "half-open" // 冷却结束：半开，放行一个探针
			return true
		}
		return false
	case "half-open":
		return true
	default:
		return true
	}
}

// Success 调用成功：复位计数并回到 closed
func (b *Breaker) Success() {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.failures = 0
	b.state = "closed"
}

// Failure 调用失败：达阈值打开；半开探针失败立即重新打开
func (b *Breaker) Failure() {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.state == "half-open" {
		b.openLocked()
		return
	}
	b.failures++
	if b.failures >= b.threshold {
		b.openLocked()
	}
}

func (b *Breaker) openLocked() {
	b.state = "open"
	b.openedAt = time.Now()
	b.failures = 0
}

// State 当前状态（测试/观测/调度跳过用）
func (b *Breaker) State() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.state
}
