// 来源：ph21-iot-vehicle-edge examples/ex05-edge-gateway/main.go
// 一句话说明：演示主程序——假云端（内存，带批幂等与 ack 水位）+ 边缘网关：
// 车辆采样 → 聚合满批上行；人为制造"断网窗口"（期间批入 spool）→ 恢复后 flush
// 按序补传 → 水位推进到全部确认。全程离线可测、输出可断言（主文档 3.11/4.3）。
// 用法：go run .
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，输出见下方预期）
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"os"
	"time"
)

// fakeCloud 内存假云端：按 gateway+batchID 幂等去重，回 ack 水位。
type fakeCloud struct {
	offline bool // 模拟断网
	seen    map[uint64]bool
	ack     uint64
}

func newFakeCloud() *fakeCloud { return &fakeCloud{seen: map[uint64]bool{}} }

func (c *fakeCloud) SendBatch(_ context.Context, b Batch) (uint64, error) {
	if c.offline {
		return c.ack, errors.New("模拟断网：上行通道不可达")
	}
	if !c.seen[b.BatchID] { // 幂等：同一批只生效一次
		c.seen[b.BatchID] = true
		if b.BatchID == c.ack+1 {
			c.ack = b.BatchID // 顺序到达 → 水位前进
		}
	}
	return c.ack, nil
}

func main() {
	l := log.New(os.Stdout, "", log.Ltime)
	cloud := newFakeCloud()
	gw := NewGateway("edge-001", 32, cloud, l)

	// 聚合器满 3 条出一批。
	flushCount := 0
	col := NewCollector("edge-001", 3, func(b Batch) {
		flushCount++
		gw.HandleBatch(b)
	})

	// 阶段 1：正常上行 6 条（2 批）。
	fmt.Println("== 阶段 1：网络正常，聚合上行 ==")
	for i := 1; i <= 6; i++ {
		col.Add(Sample{Vin: "veh-001", Seq: uint64(i), Speed: float64(30 + i), Ts: time.Now().Unix()})
	}
	sent, queued := gw.Stats()
	fmt.Printf("阶段 1 结果：上行 %d 批，入 spool %d 批\n", sent, queued)

	// 阶段 2：断网窗口，再采 9 条（3 批）全部入 spool。
	fmt.Println("== 阶段 2：断网窗口，批入 spool ==")
	cloud.offline = true
	for i := 7; i <= 15; i++ {
		col.Add(Sample{Vin: "veh-001", Seq: uint64(i), Speed: float64(30 + i), Ts: time.Now().Unix()})
	}
	sent, queued = gw.Stats()
	fmt.Printf("阶段 2 结果：spool 待补传 %d 批，累计入池 %d 批\n", gw.spool.Len(), queued)

	// 阶段 3：恢复联网，补传。
	fmt.Println("== 阶段 3：网络恢复，按序补传 ==")
	cloud.offline = false
	n, ok := gw.Flush(context.Background())
	fmt.Printf("阶段 3 结果：补传 %d 批，全部确认=%v，ack 水位=%d，spool 剩余=%d\n",
		n, ok, cloud.ack, gw.spool.Len())

	// 阶段 4：水位一致性——云上确认批数应等于累计生成批数。
	total := flushCount
	fmt.Printf("== 汇总：生成批 %d / 云端确认 %d（水位 %d）==\n", total, len(cloud.seen), cloud.ack)
	if int(cloud.ack) == total && gw.spool.Len() == 0 {
		fmt.Println("== ex05 演示完成：本地聚合 / 断网缓存 / 断点续传 / 水位归零 全通 ==")
	} else {
		fmt.Println("== 演示未对齐（数据丢失或水位未收敛），请检查 ==")
	}
}
