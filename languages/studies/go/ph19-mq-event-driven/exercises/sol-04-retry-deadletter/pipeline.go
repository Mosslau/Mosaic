// 来源：ph19-mq-event-driven exercises/sol-04-retry-deadletter（练习 4 参考实现）
// 一句话说明："重投 + attempts 计数"式的重试/死信处理——处理失败的消息带着已试次数
// 重新入队（真实工程即"重试 topic / 延迟队列"），达到上限或遇到毒消息则进 DLQ。
// 与 examples/ex03 的进程内状态机互补：这里的 attempt 信息随消息走，天然支持
// 多实例接管后继续计数（主文档 3.6）。
// 真 broker 切换：把 pending 换成 Kafka 的 retry topic（写回时 key 不变、payload 的
// attempts+1），超限发布到 dead-letter topic——消费逻辑与错误分类原样保留。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"errors"
	"fmt"
	"time"
)

// Job 一条待处理作业：Attempts 已尝试次数随消息流转（重投不丢失）。
type Job struct {
	ID       string
	Payload  string
	Attempts int
}

// ErrPoison 毒消息哨兵：解码失败/业务上永远不可能成功——不重试。
var ErrPoison = errors.New("poison job: retry cannot help")

// Handler 处理函数：返回 nil 成功；返回 ErrPoison 或包装链含 ErrPoison 判毒；
// 其余错误视为可重试。
type Handler func(Job) error

// DLQEntry 死信：原因分类（poison/exhausted）+ 已尝试次数。
type DLQEntry struct {
	Job    Job
	Reason string
	Poison bool // 便于测试/监控统计
}

// Report 一轮消费的统计。
type Report struct {
	Processed int
	Retried   int
	Dead      int
}

// Pipeline 重试/死信流水线：从初始队列逐条消费，失败重投（Attempts+1），
// 毒消息立即死信，次数耗尽死信。
type Pipeline struct {
	maxAttempts int
	backoff     func(int) time.Duration // 第 N 次重试前等待（注入时钟；测试传 nil 即不等）
	sleep       func(time.Duration)
	handler     Handler
	dlq         []DLQEntry
}

// NewPipeline 构造：maxAttempts<=0 视为 1；handler 为业务处理函数。
func NewPipeline(maxAttempts int, handler Handler) *Pipeline {
	if maxAttempts <= 0 {
		maxAttempts = 1
	}
	return &Pipeline{
		maxAttempts: maxAttempts,
		handler:     handler,
		backoff:     func(n int) time.Duration { return time.Duration(n) * time.Millisecond },
		sleep:       func(time.Duration) {}, // 默认不真睡（本示例以逻辑为主；真实服务注入 time.Sleep）
	}
}

// WithBackoff 覆写退避与等待器（测试用）。
func (p *Pipeline) WithBackoff(fn func(int) time.Duration, sleep func(time.Duration)) *Pipeline {
	p.backoff = fn
	p.sleep = sleep
	return p
}

// Run 处理初始队列直到队列清空（含重投）。
func (p *Pipeline) Run(initial []Job) Report {
	pending := append([]Job(nil), initial...)
	var rep Report
	for i := 0; i < len(pending); i++ {
		j := pending[i]
		err := p.handler(j)
		switch {
		case err == nil:
			rep.Processed++
		case errors.Is(err, ErrPoison):
			p.dlq = append(p.dlq, DLQEntry{Job: j, Reason: "毒消息（不可重试）", Poison: true})
			rep.Dead++
		default:
			if j.Attempts+1 >= p.maxAttempts { // 这次失败已无额度
				p.dlq = append(p.dlq, DLQEntry{Job: j,
					Reason: fmt.Sprintf("重试耗尽（已试 %d 次）: %v", j.Attempts+1, err)})
				rep.Dead++
				continue
			}
			p.sleep(p.backoff(j.Attempts + 1))
			j.Attempts++ // 计数随消息：重投后任何实例都能续算
			pending = append(pending, j)
			rep.Retried++
		}
	}
	return rep
}

// DLQ 返回死信列表（副本）。
func (p *Pipeline) DLQ() []DLQEntry { return append([]DLQEntry(nil), p.dlq...) }
