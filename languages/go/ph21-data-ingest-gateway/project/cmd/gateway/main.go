// 来源：ph21-data-ingest-gateway project/cmd/collector/main.go
// 一句话说明：采集代理进程入口——env 配置 + 模拟数据源集群采集（本地聚合）+ 上行 +
// 断网缓存补传循环。默认常驻（Ctrl-C 优雅退出）；-once 跑一轮确定性演示后退出。
// 运行示例：
//
//	go run ./cmd/collector -once -cloud http://127.0.0.1:8080 \
//	  -collector-id relay-001 -secret dev-secret-1 -sources 3 -samples 6
//
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测：vet/build/test 全绿；运行需有本地云端）
package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os/signal"
	"syscall"
	"time"

	"tenetlang/go/ph21-data-ingest-gateway/project/internal/collector"
	"tenetlang/go/ph21-data-ingest-gateway/project/internal/model"
)

func main() {
	log.SetFlags(log.LstdFlags | log.Lmsgprefix)
	log.SetPrefix("[collector] ")
	cloud := flag.String("cloud", "http://127.0.0.1:8080", "云端接入 URL")
	collectorID := flag.String("collector-id", "relay-001", "采集器 ID")
	secret := flag.String("secret", "dev-secret-1", "采集器密钥（与云端 GATEWAY_SECRETS 对应）")
	sources := flag.Int("sources", 3, "模拟数据源数")
	samples := flag.Int("samples", 6, "每个数据源上报样本数")
	flushSize := flag.Int("flush-size", 3, "本地聚合满多少条出一批")
	spoolCap := flag.Int("spool-cap", 64, "断网缓存容量（批）")
	once := flag.Bool("once", false, "跑一轮确定性演示后退出")
	flag.Parse()

	up := collector.NewHTTPUplink(*cloud, *collectorID, *secret)
	gw := collector.NewRelay(*collectorID, *spoolCap, up, log.Default())
	col := collector.NewCollector(*flushSize, gw.HandleBatch)

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	run := func() {
		for v := 1; v <= *sources; v++ {
			sourceID := fmt.Sprintf("veh-%03d", v)
			for s := 1; s <= *samples; s++ {
				col.Add(*collectorID, model.Sample{
					SourceID: sourceID, Seq: uint64(v*1000 + s),
					Value: 10 + float64(s)*2, // 原始计数（0.1% 单位，100..280 → 10.0%..28.0%）
					Ts:    time.Now().Unix(),
				})
			}
		}
		n, all := gw.Flush(ctx) // 先把 spool 里可能的历史批补完，再补这轮（若上行失败会入 spool）
		sent, queued, rejected := gw.Stats()
		log.Printf("本轮完成：直接/补传成功 %d 批，补传全部确认=%v，spool 待传 %d",
			n, all, gw.Pending())
		log.Printf("累计：上行成功 %d 批 / 入池 %d 批 / 被拒 %d 批", sent, queued, rejected)
	}

	if *once {
		run()
		return
	}
	// 常驻：每 10s 采一轮 + 补传（演示采集器生命周期）。
	for {
		run()
		select {
		case <-ctx.Done():
			log.Println("收到退出信号")
			return
		case <-time.After(10 * time.Second):
		}
	}
}
