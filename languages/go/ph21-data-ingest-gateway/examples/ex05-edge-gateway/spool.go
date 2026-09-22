// 来源：ph21-data-ingest-gateway examples/ex05-edge-gateway/spool.go
// 一句话说明：断网缓存队列（有界）——上行失败的批按 batchID 递增顺序入队；
// AckUpTo 按云端水位裁剪已确认前缀。容量上限先于一切：放不下按策略拒绝
// （真实网关会先丢可重算遥测批、保留不可重算事件，主文档 3.11/4.3）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"errors"
	"fmt"
	"sync"
)

// ErrSpoolFull 缓存满。
var ErrSpoolFull = errors.New("spool: 缓存已满")

// Spool 有界断网缓存。批次在队内按 BatchID 升序，补传严格按序重放。
type Spool struct {
	maxItems int
	mu       sync.Mutex
	items    []Batch // 队首是最旧未确认批
	ackSeq   uint64  // 已确认水位：< = 该值的 batch 已从队列剪掉
}

// NewSpool 建容量上限为 maxItems 的缓存。
func NewSpool(maxItems int) *Spool {
	return &Spool{maxItems: maxItems}
}

// Enqueue 入队（调用方保证新批 BatchID 大于队内全部——Collector 的 nextID 天然递增）。
func (s *Spool) Enqueue(item Batch) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.items) >= s.maxItems {
		return fmt.Errorf("%w: 已存 %d 批", ErrSpoolFull, s.maxItems)
	}
	s.items = append(s.items, item)
	return nil
}

// Pending 返回待补传批次（副本，按 BatchID 升序）。
func (s *Spool) Pending() []Batch {
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([]Batch(nil), s.items...)
}

// Len 待补传批数。
func (s *Spool) Len() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.items)
}

// AckUpTo 云端确认水位推进：BatchID <= seq 的批全部确认，物理裁剪。
// 裁剪滞后于水位（这里同一次调用执行；真实网关批量/定时裁剪，主文档 4.3）。
func (s *Spool) AckUpTo(seq uint64) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if seq <= s.ackSeq {
		return // 水位只进不退
	}
	s.ackSeq = seq
	keep := 0
	for keep < len(s.items) && s.items[keep].BatchID <= seq {
		keep++
	}
	s.items = s.items[keep:]
}

// AckSeq 当前确认水位（断点续传从这里继续）。
func (s *Spool) AckSeq() uint64 {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.ackSeq
}
