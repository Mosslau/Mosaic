// 来源：ph19-mq-event-driven examples/ex03-retry-deadletter/dlq.go
// 一句话说明：死信队列（DLQ）——重试失败或不可重试的消息的归宿。
// DLQ 让"消费彻底失败的证据"不丢：人工/补偿任务可以重放，也可观测死信增长
// 反推上游数据质量问题（主文档 3.6/3.7）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"fmt"
	"sync"
)

// DLQEntry 一条死信：原始消息 + 死亡原因 + 已尝试次数。
// Reason 是人可读的排查线索；保留原始 Payload 以便重放工具原样重投。
type DLQEntry struct {
	Message  Message
	Reason   string
	Attempts int
}

// DLQ 线程安全的死信队列（内存实现；真实工程通常是一个专门 topic/表）。
type DLQ struct {
	mu    sync.Mutex
	items []DLQEntry
}

// NewDLQ 建空死信队列。
func NewDLQ() *DLQ { return &DLQ{} }

// Add 追加一条死信。
func (d *DLQ) Add(msg Message, reason string, attempts int) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.items = append(d.items, DLQEntry{Message: msg, Reason: reason, Attempts: attempts})
}

// Len 死信条数（监控指标：死信涨得快 = 上游质量或规则问题，见主文档 3.7）。
func (d *DLQ) Len() int {
	d.mu.Lock()
	defer d.mu.Unlock()
	return len(d.items)
}

// Entries 返回全部死信副本（供打印/重放）。
func (d *DLQ) Entries() []DLQEntry {
	d.mu.Lock()
	defer d.mu.Unlock()
	return append([]DLQEntry(nil), d.items...)
}

// Replay 重放一条死信回正常处理（补偿路径的钩子；本示例只留接口形状）。
func (d *DLQ) Replay(entry DLQEntry) string {
	return fmt.Sprintf("replay %s → topic:retry（真实工程重投到 retry topic，带原 Attempts）", entry.Message.ID)
}
