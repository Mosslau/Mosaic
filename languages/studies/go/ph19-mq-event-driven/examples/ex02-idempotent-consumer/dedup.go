// 来源：ph19-mq-event-driven examples/ex02-idempotent-consumer/dedup.go
// 一句话说明：有界去重表——消息队列不保证"恰好一次"，consumer 必须自己
// 用幂等键（这里取事件的 MsgID）把重复投递挡在副作用之外（主文档 3.5）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import "sync"

// Deduper 一个容量受限的"最近见过"去重表：map 负责 O(1) 查询，
// 插入顺序队列负责容量回收（FIFO：超容量先淘汰最早记的键）。
// 真实工程里这张表常落在 Redis/DB（带 TTL），而非进程内存——
// 进程内存意味着重启丢表，重启期间的重复投递会漏网。
type Deduper struct {
	mu    sync.Mutex
	max   int
	order []string            // 键的插入顺序（队首最早）
	seen  map[string]struct{} // 见过去重键
}

// NewDeduper 建一张最多记住 max 个键的去重表（max<=0 时记忆无限）。
func NewDeduper(max int) *Deduper {
	if max <= 0 {
		max = 1 << 30
	}
	return &Deduper{
		max:  max,
		seen: make(map[string]struct{}),
	}
}

// Seen 报告键是否已经处理过（去重判定）。
func (d *Deduper) Seen(key string) bool {
	d.mu.Lock()
	defer d.mu.Unlock()
	_, ok := d.seen[key]
	return ok
}

// Mark 记录一个已处理键，超容量时淘汰最旧的。
func (d *Deduper) Mark(key string) {
	d.mu.Lock()
	defer d.mu.Unlock()
	if _, ok := d.seen[key]; ok {
		return // 已记过：不重复排队（也防止 order 无限长）
	}
	d.seen[key] = struct{}{}
	d.order = append(d.order, key)
	for len(d.order) > d.max {
		delete(d.seen, d.order[0])
		d.order = d.order[1:] // 队首出列（切片头移动；量级见主文档 4 章说明）
	}
}

// Len 当前记忆的键数（打印观察用）。
func (d *Deduper) Len() int {
	d.mu.Lock()
	defer d.mu.Unlock()
	return len(d.order)
}
