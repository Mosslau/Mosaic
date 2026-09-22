// 来源：ph19-mq-event-driven examples/ex03-retry-deadletter/retry.go
// 一句话说明：有界重试 + 退避 + 死信的有穷状态机。消息处理失败后不是无限
// 重试拖死消费者，而是按状态机流转：Processing ─失败─▶ RetryWait ─次数耗尽─▶ Dead。
// 关键设计：可重试错误与毒消息（poison，重试无意义）必须分开（主文档 3.6）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"errors"
	"fmt"
	"sync"
	"time"
)

// Message 一条待处理消息。
type Message struct {
	ID      string
	Payload string
}

// 错误分类：错误值即状态机的转移信号。
var (
	// ErrPoison 毒消息哨兵：解码不了/业务上永远无法成功——重试无意义。
	// 用 errors.Is 判定（golang-patterns：错误比较走哨兵，不靠字符串）。
	ErrPoison = errors.New("poison message: retrying will not help")
)

// Retryable 把一个底层错误包装为"可重试"类别（%w 保链，errors.Is/As 可达）。
func Retryable(cause error) error {
	return fmt.Errorf("retryable: %w", cause)
}

// Outcome 一条消息的最终结局。
type Outcome struct {
	Status   Status
	Attempts int
}

// Status 三态：成功 / 耗尽进死信 / 毒消息进死信。
type Status int

const (
	StatusDone Status = iota // 处理成功
	StatusDead               // 进入死信队列
)

func (s Status) String() string {
	if s == StatusDone {
		return "done"
	}
	return "dead"
}

// Config 重试策略：次数上限 + 退避函数 + 可注入的等待器（测试传空实现避免真睡）。
type Config struct {
	MaxAttempts int                     // 最大尝试次数（含第一次）；<=0 视为 1
	Backoff     func(int) time.Duration // 第 N 次重试前等多久（N 从 1 起）
	sleep       func(time.Duration)     // 可注入；nil = time.Sleep
}

// Pipeline 执行"处理→重试→死信"状态机的入口。线程安全（DLQ 有锁）。
type Pipeline struct {
	cfg  Config
	dlq  *DLQ
	mu   sync.Mutex
	done int // 成功条数（观察用）
}

// NewPipeline 构造流水线。
func NewPipeline(cfg Config, dlq *DLQ) *Pipeline {
	if cfg.MaxAttempts <= 0 {
		cfg.MaxAttempts = 1
	}
	if cfg.Backoff == nil {
		cfg.Backoff = func(int) time.Duration { return 0 }
	}
	if cfg.sleep == nil {
		cfg.sleep = time.Sleep
	}
	return &Pipeline{cfg: cfg, dlq: dlq}
}

// Handle 处理一条消息并返回结局。do 是"真正可能失败"的处理动作；
// 它返回的 error 决定转移：nil=成功、ErrPoison 或包装链含 ErrPoison=毒消息、
// 其他=可重试。
func (p *Pipeline) Handle(msg Message, do func(Message) error) Outcome {
	attempts := 0
	var lastErr error
	for attempts < p.cfg.MaxAttempts {
		if attempts > 0 {
			p.cfg.sleep(p.cfg.Backoff(attempts)) // 先退避再重试
		}
		lastErr = do(msg)
		if lastErr == nil {
			p.mu.Lock()
			p.done++
			p.mu.Unlock()
			return Outcome{Status: StatusDone, Attempts: attempts + 1}
		}
		attempts++
		if errors.Is(lastErr, ErrPoison) {
			break // 毒消息：立即进死信，不浪费剩余重试
		}
	}
	p.dlq.Add(msg, classify(msg, lastErr, attempts), attempts)
	return Outcome{Status: StatusDead, Attempts: attempts}
}

// Done 统计成功条数。
func (p *Pipeline) Done() int {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.done
}

// classify 给死信条目标注"为什么死"：毒消息 vs 重试耗尽——排查两类问题的路径不同。
func classify(msg Message, err error, attempts int) string {
	if errors.Is(err, ErrPoison) {
		return fmt.Sprintf("毒消息（不可重试）: %v", err)
	}
	return fmt.Sprintf("重试 %d 次仍失败（可重试错误耗尽）: %v", attempts-1, err)
}
