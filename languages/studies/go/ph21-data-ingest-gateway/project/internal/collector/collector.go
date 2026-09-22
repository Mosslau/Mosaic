// 来源：ph21-data-ingest-gateway project/internal/collector/collector.go
// 一句话说明：采集代理核心——本地聚合出批、上行接口抽象、有界断网缓存(spool)、
// 按序补传与 ack 水位推进。传输层在 transport.go（HTTP），换 MQTT 只需新实现
// Uplink（主文档 3.11/4.3）。与 examples/ex05 同构，这里直接落在 model 线格式上。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package collector

import (
	"context"
	"errors"
	"fmt"
	"log"
	"sync"
	"sync/atomic"
	"time"

	"tenetlang/go/ph21-data-ingest-gateway/project/internal/auth"
	"tenetlang/go/ph21-data-ingest-gateway/project/internal/model"
)

// ErrSpoolFull 断网缓存满（丢弃策略由调用方决定）。
var ErrSpoolFull = errors.New("collector: spool 满")

// Uplink 上行通道抽象（HTTP/MQTT/测试桩都可实现）。
type Uplink interface {
	// SendBatch 成功返回云端确认水位；鉴权失败返回 auth.ErrUnauthorized（不可重试）。
	SendBatch(ctx context.Context, b model.BatchUpload) (ack uint64, err error)
}

// Collector 本地聚合：同数据源样本攒批满 flushSize 触发回调。
type Collector struct {
	FlushSize int
	Flush     func(model.BatchUpload)
	mu        sync.Mutex
	buf       map[string][]model.Sample
	nextID    uint64
}

// NewCollector 建聚合器（batchID 从 1 起）。
func NewCollector(flushSize int, flush func(model.BatchUpload)) *Collector {
	return &Collector{
		FlushSize: flushSize,
		Flush:     flush,
		buf:       make(map[string][]model.Sample),
		nextID:    1,
	}
}

// Add 收样本，满批 flush。
func (c *Collector) Add(collectorID string, s model.Sample) {
	c.mu.Lock()
	c.buf[s.SourceID] = append(c.buf[s.SourceID], s)
	if len(c.buf[s.SourceID]) >= c.FlushSize {
		b := model.BatchUpload{CollectorID: collectorID, BatchID: c.nextID, Samples: c.buf[s.SourceID]}
		c.nextID++
		c.buf[s.SourceID] = nil
		c.mu.Unlock()
		c.Flush(b)
		return
	}
	c.mu.Unlock()
}

// Spool 有界断网缓存（batchID 升序，水位裁剪）。
type Spool struct {
	maxItems int
	mu       sync.Mutex
	items    []model.BatchUpload
	ackSeq   uint64
}

// NewSpool 建缓存。
func NewSpool(maxItems int) *Spool { return &Spool{maxItems: maxItems} }

// Enqueue 入队。
func (s *Spool) Enqueue(b model.BatchUpload) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.items) >= s.maxItems {
		return fmt.Errorf("%w: %d 批", ErrSpoolFull, s.maxItems)
	}
	s.items = append(s.items, b)
	return nil
}

// Pending 待补传批（升序副本）。
func (s *Spool) Pending() []model.BatchUpload {
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([]model.BatchUpload(nil), s.items...)
}

// Len 待补传批数。
func (s *Spool) Len() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.items)
}

// AckUpTo 水位推进并裁剪已确认前缀（只进不退）。
func (s *Spool) AckUpTo(seq uint64) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if seq <= s.ackSeq {
		return
	}
	s.ackSeq = seq
	keep := 0
	for keep < len(s.items) && s.items[keep].BatchID <= seq {
		keep++
	}
	s.items = s.items[keep:]
}

// AckSeq 当前确认水位（断点续传起点）。
func (s *Spool) AckSeq() uint64 {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.ackSeq
}

// Relay 采集代理（原采集代理）：本地聚合、断网入 spool、恢复后补传。
type Relay struct {
	ID     string
	uplink Uplink
	spool  *Spool
	sent   atomic.Int64
	queued atomic.Int64
	reject atomic.Int64 // 鉴权/不可重试失败丢弃数
	mu     chan struct{}
	log    *log.Logger
}

// NewRelay 建采集器。
func NewRelay(id string, spoolCap int, up Uplink, l *log.Logger) *Relay {
	return &Relay{
		ID: id, uplink: up, spool: NewSpool(spoolCap),
		mu: make(chan struct{}, 1), log: l,
	}
}

// HandleBatch 聚合器回调：上行失败入 spool；鉴权失败丢弃不重试。
func (g *Relay) HandleBatch(b model.BatchUpload) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	ack, err := g.uplink.SendBatch(ctx, b)
	if err == nil {
		g.sent.Add(1)
		g.log.Printf("采集器 %s: 批 %d 上行成功（水位 %d）", g.ID, b.BatchID, ack)
		return
	}
	if errors.Is(err, auth.ErrUnauthorized) {
		g.reject.Add(1)
		g.log.Printf("采集器 %s: 批 %d 被拒（鉴权失败，不重试）: %v", g.ID, b.BatchID, err)
		return
	}
	if serr := g.spool.Enqueue(b); serr != nil {
		g.log.Printf("采集器 %s: spool 满，批 %d 按丢弃策略放弃: %v", g.ID, b.BatchID, serr)
		return
	}
	g.queued.Add(1)
	g.log.Printf("采集器 %s: 网络失败，批 %d 入 spool 待补传: %v", g.ID, b.BatchID, err)
}

// Flush 按序补传全部待确认批。
func (g *Relay) Flush(ctx context.Context) (int, bool) {
	g.mu <- struct{}{}
	defer func() { <-g.mu }()
	pending := g.spool.Pending()
	sent := 0
	for _, b := range pending {
		if err := ctx.Err(); err != nil {
			break
		}
		ack, err := g.uplink.SendBatch(ctx, b)
		if err != nil {
			if errors.Is(err, auth.ErrUnauthorized) {
				g.reject.Add(1)
			}
			g.log.Printf("采集器 %s: 补传批 %d 失败: %v", g.ID, b.BatchID, err)
			break // 断点续传：失败处停下重试
		}
		sent++
		g.spool.AckUpTo(ack)
		g.log.Printf("采集器 %s: 补传批 %d 成功（水位 %d，待传 %d）", g.ID, b.BatchID, ack, g.spool.Len())
	}
	return sent, g.spool.Len() == 0
}

// Stats 返回 (上行成功批, 入池批, 被拒批)。
func (g *Relay) Stats() (sent, queued, rejected int64) {
	return g.sent.Load(), g.queued.Load(), g.reject.Load()
}

// Pending 待补传数（运维/测试视图）。
func (g *Relay) Pending() int { return g.spool.Len() }
