// 来源：ph21-iot-vehicle-edge examples/ex06-telemetry-platform/main.go
// 一句话说明：演示主程序——确定性车流 6 条：2 条正常(30/90km/h)、1 条超速
// (135km/h→warn)、1 条超速(180km/h→critical)、1 条坏数据(超量程→死信)、
// 1 条重复(seq 重复→幂等拦)。随后打印时序查询、实时状态、/metrics 文本、汇总。
// 用法：go run .
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，输出见下方预期）
package main

import (
	"fmt"
	"net/http/httptest"
	"time"
)

func main() {
	p := NewPlatform()
	p.Metrics.SetOnline(2)
	now := time.Now()

	feed := []Event{
		{Vin: "veh-001", Seq: 1, Speed: 30.0 / 3.6, Ts: now.Add(time.Second)},
		{Vin: "veh-001", Seq: 2, Speed: 90.0 / 3.6, Ts: now.Add(2 * time.Second)},
		{Vin: "veh-001", Seq: 3, Speed: 135.0 / 3.6, Ts: now.Add(3 * time.Second)},
		{Vin: "veh-001", Seq: 4, Speed: 180.0 / 3.6, Ts: now.Add(4 * time.Second)},
		{Vin: "veh-001", Seq: 5, Speed: 999.0, Ts: now.Add(5 * time.Second)},      // 超量程坏数据
		{Vin: "veh-001", Seq: 1, Speed: 30.0 / 3.6, Ts: now.Add(6 * time.Second)}, // 重复
	}
	for _, ev := range feed {
		if err := p.Ingest(ev); err != nil {
			fmt.Printf("[死信] %s\n", err)
		}
	}

	// 查询面：最新值 / 实时状态。
	latest, _ := p.Store.Latest("veh-001", "speed")
	fmt.Printf("最新车速: %.1f km/h\n", latest.Value)
	st, _ := p.Status.Latest("veh-001")
	fmt.Printf("实时状态: %v\n", st)
	buckets := p.Store.RangeAggregate("speed", now, now.Add(6*time.Second), 2*time.Second)
	for _, b := range buckets {
		fmt.Printf("聚合桶 %s: avg=%.1f max=%.1f hits=%d\n", b.Ts.Format("15:04:05"), b.Avg, b.Max, b.Hits)
	}

	// /metrics 文本端点（真 Prometheus 抓的就是这个文本，格式见主文档 3.9）。
	rec := httptest.NewRecorder()
	p.Metrics.ServeHTTP(rec, nil)
	fmt.Println("== /metrics 输出 ==")
	fmt.Print(rec.Body.String())
	fmt.Println("== 汇总 ==")
	fmt.Println(p.Summary())
}
