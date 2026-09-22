// 来源：ph21-data-ingest-gateway project/cmd/gateway/main.go
// 一句话说明：边缘网关进程入口——env 配置 + 模拟车队采集（本地聚合）+ 上行 +
// 断网缓存补传循环。默认常驻（Ctrl-C 优雅退出）；-once 跑一轮确定性演示后退出。
// 运行示例：
//
//	go run ./cmd/gateway -once -cloud http://127.0.0.1:8080 \
//	  -gateway-id edge-001 -secret dev-secret-1 -vehicles 3 -samples 6
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

	"tenetlang/go/ph21-data-ingest-gateway/project/internal/gateway"
	"tenetlang/go/ph21-data-ingest-gateway/project/internal/model"
)

func main() {
	log.SetFlags(log.LstdFlags | log.Lmsgprefix)
	log.SetPrefix("[gateway] ")
	cloud := flag.String("cloud", "http://127.0.0.1:8080", "云端接入 URL")
	gatewayID := flag.String("gateway-id", "edge-001", "网关 ID")
	secret := flag.String("secret", "dev-secret-1", "网关密钥（与云端 GATEWAY_SECRETS 对应）")
	vehicles := flag.Int("vehicles", 3, "模拟车辆数")
	samples := flag.Int("samples", 6, "每辆车上报样本数")
	flushSize := flag.Int("flush-size", 3, "本地聚合满多少条出一批")
	spoolCap := flag.Int("spool-cap", 64, "断网缓存容量（批）")
	once := flag.Bool("once", false, "跑一轮确定性演示后退出")
	flag.Parse()

	up := gateway.NewHTTPUplink(*cloud, *gatewayID, *secret)
	gw := gateway.NewGateway(*gatewayID, *spoolCap, up, log.Default())
	col := gateway.NewCollector(*flushSize, gw.HandleBatch)

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	run := func() {
		for v := 1; v <= *vehicles; v++ {
			vin := fmt.Sprintf("veh-%03d", v)
			for s := 1; s <= *samples; s++ {
				col.Add(*gatewayID, model.Sample{
					Vin: vin, Seq: uint64(v*1000 + s),
					Speed: 10 + float64(s)*2, // m/s（10..30 m/s ≈ 36..108 km/h）
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
	// 常驻：每 10s 采一轮 + 补传（演示网关生命周期）。
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
