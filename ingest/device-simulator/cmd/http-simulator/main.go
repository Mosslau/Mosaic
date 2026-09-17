// Command simulator 模拟车端设备产生器: 用 N 个并发"虚拟车辆"按固定频率
// 向网关上报数据, 用于链路联调与压测。
//
// 用法示例(1 万设备, 每设备每 5 秒一条, 跑 60 秒):
//
//	go run ./cmd/simulator -devices 10000 -interval 5s -duration 60s
//
// 压测前请确保网关以 GATEWAY_DEV_MODE=true 启动(接受 dev- 前缀 token)。
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"math/rand/v2"
	"net/http"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/Mosslau/OceanVerse/ingest/device-contracts/vehicle"
	"github.com/Mosslau/OceanVerse/ingest/device-simulator/internal/simdata"
)

var (
	target   = flag.String("target", "http://localhost:8080", "网关地址")
	devices  = flag.Int("devices", 100, "模拟设备数")
	interval = flag.Duration("interval", 5*time.Second, "单设备上报间隔")
	duration = flag.Duration("duration", 60*time.Second, "压测总时长 (0=不限, Ctrl+C 停止)")
)

var (
	sentOK   atomic.Int64
	sentFail atomic.Int64
	bytesIn  atomic.Int64
)

func main() {
	flag.Parse()

	client := &http.Client{
		Timeout: 10 * time.Second,
		Transport: &http.Transport{
			MaxIdleConns:        1024,
			MaxIdleConnsPerHost: 256,
			IdleConnTimeout:     90 * time.Second,
		},
	}

	ctx, cancel := context.WithCancel(context.Background())
	if *duration > 0 {
		ctx, cancel = context.WithTimeout(ctx, *duration)
	}
	defer cancel()
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	go func() { <-sig; cancel() }()

	fmt.Printf("模拟 %d 台设备, 间隔 %v, 目标 %s\n", *devices, *interval, *target)
	start := time.Now()

	// 启动所有虚拟设备
	done := make(chan struct{})
	step := (*devices + 255) / 256 // 分批启动防瞬时惊群打爆本机
	for batch := 0; batch < *devices; batch += step {
		end := min(batch+step, *devices)
		go func(lo, hi int) {
			for i := lo; i < hi; i++ {
				go runDevice(ctx, client, i)
			}
		}(batch, end)
		time.Sleep(100 * time.Millisecond) // 每批间隔 100ms 爬坡
	}

	// 每 5 秒打印一次统计
	tick := time.NewTicker(5 * time.Second)
	defer tick.Stop()
	var lastOK, lastFail int64
loop:
	for {
		select {
		case <-ctx.Done():
			break loop
		case <-tick.C:
			ok, fail := sentOK.Load(), sentFail.Load()
			fmt.Printf("[%6.0fs] ok=%d fail=%d  近5s qps=%.1f\n",
				time.Since(start).Seconds(), ok, fail, float64(ok-lastOK+fail-lastFail)/5)
			lastOK, lastFail = ok, fail
		}
	}
	close(done)

	elapsed := time.Since(start).Seconds()
	fmt.Printf("\n===== 压测结束 =====\n")
	fmt.Printf("时长: %.0fs, 成功: %d, 失败: %d, 平均 QPS: %.1f\n",
		elapsed, sentOK.Load(), sentFail.Load(), float64(sentOK.Load())/elapsed)
	if sentFail.Load() > 0 {
		fmt.Printf("⚠️  有失败请求, 检查网关日志与 metrics 中 result 标签分布\n")
	}
}

// runDevice 一台虚拟车辆的生命周期: 定时上报直到 ctx 取消
func runDevice(ctx context.Context, client *http.Client, id int) {
	vin := fmt.Sprintf("OV%08d", id)
	token := "dev-" + vin
	rng := rand.New(rand.NewPCG(uint64(id), uint64(id>>32)))

	// 每台车随机相位, 避免所有设备同刻发送
	jitter := time.Duration(rng.Int64N(int64(*interval)))
	t := time.NewTimer(jitter)
	select {
	case <-ctx.Done():
		t.Stop()
		return
	case <-t.C:
	}

	ticker := time.NewTicker(*interval)
	defer ticker.Stop()
	soc := 60 + rng.Float64()*40 // 初始电量 60~100

	for {
		report := simdata.BuildVehicleStatus(vin, rng, &soc)
		send(ctx, client, report, token)
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}

// send 发送一条上报并统计结果。
// 只有 202 计成功: 被限流(429)/被拒(400/401)也算失败——压测要看到真实的拒绝率,
// 否则限流策略把请求掐了、报表上还显示"100% 成功"。
func send(ctx context.Context, client *http.Client, r *vehicle.VehicleReport, token string) {
	body, err := json.Marshal(r)
	if err != nil {
		sentFail.Add(1)
		return
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, *target+"/api/v1/vehicle/report", bytes.NewReader(body))
	if err != nil {
		sentFail.Add(1)
		return
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Device-Token", token)

	resp, err := client.Do(req)
	if err != nil {
		sentFail.Add(1)
		return
	}
	defer resp.Body.Close()
	n, _ := io.Copy(io.Discard, resp.Body)
	bytesIn.Add(n)
	if resp.StatusCode == http.StatusAccepted {
		sentOK.Add(1)
	} else {
		sentFail.Add(1)
	}
}
