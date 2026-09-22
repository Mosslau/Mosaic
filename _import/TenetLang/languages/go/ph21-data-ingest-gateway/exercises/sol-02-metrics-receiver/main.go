// 来源：ph21-data-ingest-gateway exercises/sol-02-metrics-receiver/main.go
// 一句话说明：练习 2 演示——喂入 8 条报文：4 条有效（含需换算的量值）、1 条缺 sourceID、
// 1 条超量程、1 条重复、1 条乱序；打印三路计数与换算结果。
// 用法：go run .
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，输出见下方预期）
package main

import "fmt"

func main() {
	r := NewReceiver(100)
	feed := []string{
		`{"sourceID":"src-001","seq":1,"value":30.0}`,
		`{"sourceID":"src-001","seq":2,"value":50.0}`,
		`{"sourceID":"src-001","seq":3,"value":60.0}`,
		`{"sourceID":"src-001","seq":4,"value":100.0}`,
		`{"seq":5,"value":10.0}`,                      // 缺 sourceID
		`{"sourceID":"src-001","seq":6,"value":999}`,  // 超量程
		`{"sourceID":"src-001","seq":2,"value":50.0}`, // 重复
		`{"sourceID":"src-001","seq":1,"value":30.0}`, // 乱序迟到
	}
	for _, raw := range feed {
		if got, err := r.Handle([]byte(raw)); err != nil {
			fmt.Println("[拒]", err)
		} else {
			fmt.Printf("[收] %s seq=%d value=%.1f%%\n", got.SourceID, got.Seq, got.ValuePct)
		}
	}
	fmt.Println("汇总:", r.Summary())
	fmt.Println("== sol-02 演示完成 ==")
}
