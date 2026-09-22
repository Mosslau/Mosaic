// 来源：ph21-data-ingest-gateway examples/ex06-metrics-platform/main.go
// 一句话说明：演示主程序——确定性车流 6 条：2 条正常(30/90%%)、1 条超阈值
// (135%%→warn)、1 条超阈值(180%%→critical)、1 条坏数据(超量程→死信)、
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
		{SourceID: "src-001", Seq: 1, Value: 30.0 / 3.6, Ts: now.Add(time.Second)},
		{SourceID: "src-001", Seq: 2, Value: 90.0 / 3.6, Ts: now.Add(2 * time.Second)},
		{SourceID: "src-001", Seq: 3, Value: 135.0 / 3.6, Ts: now.Add(3 * time.Second)},
		{SourceID: "src-001", Seq: 4, Value: 180.0 / 3.6, Ts: now.Add(4 * time.Second)},
		{SourceID: "src-001", Seq: 5, Value: 999.0, Ts: now.Add(5 * time.Second)},      // 超量程坏数据
		{SourceID: "src-001", Seq: 1, Value: 30.0 / 3.6, Ts: now.Add(6 * time.Second)}, // 重复
	}
	for _, ev := range feed {
		if err := p.Ingest(ev); err != nil {
			fmt.Printf("[死信] %s\n", err)
		}
	}

	// 查询面：最新值 / 实时状态。
	latest, _ := p.Store.Latest("src-001", "value")
	fmt.Printf("最新采集量值: %.1f %%\n", latest.Value)
	st, _ := p.Status.Latest("src-001")
	fmt.Printf("实时状态: %v\n", st)
	buckets := p.Store.RangeAggregate("value", now, now.Add(6*time.Second), 2*time.Second)
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
