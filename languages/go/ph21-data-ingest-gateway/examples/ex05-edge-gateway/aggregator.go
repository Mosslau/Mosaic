// 来源：ph21-data-ingest-gateway examples/ex05-edge-gateway/aggregator.go
// 一句话说明：本地聚合——同车样本先攒批再上行：条数/窗口触发 flush。上行频率
// 降一个量级，云端拿到的是"批"不是"流"（主文档 3.11 边缘网关本地聚合）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import "sync"

// Collector 单网关的聚合器：按车缓冲样本，攒够 FlushSize 触发回调。
// 时间窗口触发（FlushInterval）是配套策略，离线测试只用条数触发。
type Collector struct {
	FlushSize int
	Flush     func(b Batch) // 回调由网关实现：尝试上行/失败入 spool
	GatewayID string

	mu     sync.Mutex
	buf    map[string][]Sample
	nextID uint64
}

// NewCollector 建聚合器（batchID 从 1 起：0 保留给"无批"水位）。
func NewCollector(gatewayID string, flushSize int, flush func(Batch)) *Collector {
	return &Collector{
		FlushSize: flushSize, Flush: flush, GatewayID: gatewayID,
		buf:    make(map[string][]Sample),
		nextID: 1,
	}
}

// Add 收一条样本：同车缓冲；满批则打包 flush 并分配新 batchID。
func (c *Collector) Add(s Sample) {
	c.mu.Lock()
	c.buf[s.Vin] = append(c.buf[s.Vin], s)
	if len(c.buf[s.Vin]) >= c.FlushSize {
		batch := Batch{
			BatchID:   c.nextID,
			GatewayID: c.GatewayID,
			Samples:   c.buf[s.Vin],
		}
		c.nextID++
		c.buf[s.Vin] = nil
		c.mu.Unlock()
		c.Flush(batch) // flush 在锁外：回调可能重入 Add（发送失败入 spool 后继续采）
		return
	}
	c.mu.Unlock()
}

// PendingCount 尚未 flush 的缓冲样本数（测试/运维视图）。
func (c *Collector) PendingCount() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	n := 0
	for _, v := range c.buf {
		n += len(v)
	}
	return n
}
