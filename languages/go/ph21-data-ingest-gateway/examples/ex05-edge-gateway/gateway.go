// 来源：ph21-data-ingest-gateway examples/ex05-edge-gateway/gateway.go
// 一句话说明：边缘网关主体——聚合器出批 → 尝试上行；失败入 spool；后台 flush 按
// 序补传（云端 ack 水位推进，断点续传）。Uplink 是接口（HTTP/内存假云端都可注入），
// 网关不关心上行通道是 MQTT 还是 HTTP（主文档 3.11/4.3）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"context"
	"log"
	"sync/atomic"
	"time"
)

// Uplink 上行通道抽象：SendBatch 发送一批，返回云端 ack 的连续水位。
type Uplink interface {
	// SendBatch 成功返回 (最新确认水位, nil)；瞬时网络错误返回可重试 error。
	SendBatch(ctx context.Context, b Batch) (ackSeq uint64, err error)
}

// Gateway 边缘网关。
type Gateway struct {
	ID     string
	uplink Uplink
	spool  *Spool
	sent   atomic.Int64  // 上行成功批数
	queued atomic.Int64  // 断网入 spool 批数
	mu     chan struct{} // 简易互斥（序列化 flush，防并发补传乱序）
	log    *log.Logger
}

// NewGateway 建网关（uplink 可先用失败桩，运行中断网入 spool）。
func NewGateway(id string, spoolCap int, up Uplink, l *log.Logger) *Gateway {
	return &Gateway{ID: id, uplink: up, spool: NewSpool(spoolCap), mu: make(chan struct{}, 1), log: l}
}

// HandleBatch 聚合器回调：先试上行，失败入 spool。
func (g *Gateway) HandleBatch(b Batch) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	ack, err := g.uplink.SendBatch(ctx, b)
	if err == nil {
		g.sent.Add(1)
		g.log.Printf("网关 %s: 批 %d 上行成功（水位 %d）", g.ID, b.BatchID, ack)
		return
	}
	// 网络错误：入 spool 等补传。ErrSpoolFull 时只能按丢弃策略丢（此处记日志）。
	if serr := g.spool.Enqueue(b); serr != nil {
		g.log.Printf("网关 %s: spool 满，批 %d 丢弃: %v", g.ID, b.BatchID, serr)
		return
	}
	g.queued.Add(1)
	g.log.Printf("网关 %s: 网络失败，批 %d 入 spool（待补传）: %v", g.ID, b.BatchID, err)
}

// Flush 把 spool 里所有批次按序补传；返回 (补传批数, 是否全部确认)。
func (g *Gateway) Flush(ctx context.Context) (int, bool) {
	g.mu <- struct{}{} // 只允许一个补传循环
	defer func() { <-g.mu }()

	pending := g.spool.Pending()
	sent := 0
	for _, b := range pending {
		if err := ctx.Err(); err != nil {
			break
		}
		ack, err := g.uplink.SendBatch(ctx, b)
		if err != nil {
			g.log.Printf("网关 %s: 补传批 %d 仍失败: %v", g.ID, b.BatchID, err)
			break // 断点续传：从失败的这批发起重试，不动后面的
		}
		sent++
		g.spool.AckUpTo(ack) // 水位推进 → 剪掉已确认前缀
		g.log.Printf("网关 %s: 补传批 %d 成功（水位 %d，待传 %d）", g.ID, b.BatchID, ack, g.spool.Len())
	}
	return sent, g.spool.Len() == 0
}

// Stats 返回 (上行成功批, 断网入池批)。
func (g *Gateway) Stats() (sent, queued int64) {
	return g.sent.Load(), g.queued.Load()
}
