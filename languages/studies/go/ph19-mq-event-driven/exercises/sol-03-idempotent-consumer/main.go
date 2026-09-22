// 来源：ph19-mq-event-driven exercises/sol-03-idempotent-consumer（练习 3 参考实现）
// 一句话说明：main —— 演示时间窗去重：5 个唯一事件 + 3 次重复投递（一次在窗口内、
// 一次在过期后），幂等消费后副作用只对唯一事件生效（主文档 3.5）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"fmt"
	"time"
)

func main() {
	base := time.Date(2026, 9, 1, 0, 0, 0, 0, time.UTC)
	dedup := NewDedupeWindow(10*time.Minute, 1000)
	sink := &DuplicateCounterSink{}
	c := NewIdempotentConsumer(dedup, sink)
	// 注入时钟：让"窗口过期"可控（真实系统用 time.Now）。
	now := base
	c.now = func() time.Time { return now }

	events := []VehicleEvent{
		{MsgID: "m1", CarID: "car-001", Kind: "telemetry", Data: "speed=50"},
		{MsgID: "m2", CarID: "car-001", Kind: "telemetry", Data: "speed=55"},
		{MsgID: "m3", CarID: "car-002", Kind: "alarm", Data: "battery_low"},
		{MsgID: "m4", CarID: "car-002", Kind: "telemetry", Data: "speed=40"},
		{MsgID: "m5", CarID: "car-003", Kind: "telemetry", Data: "speed=70"},
	}
	feed := func(e VehicleEvent) {
		applied, err := c.Consume(e)
		if err != nil {
			fmt.Println("   error:", err)
			return
		}
		if !applied {
			fmt.Printf("   [skip] %s 重复投递，未再生效\n", e.MsgID)
		}
	}

	fmt.Println("== 首次消费 5 个唯一事件 ==")
	for _, e := range events {
		feed(e)
		now = now.Add(time.Second)
	}
	fmt.Println("== 窗口内重复投递（m2）==")
	now = now.Add(1 * time.Minute)
	feed(events[1]) // m2 在 TTL 内重投 → skip
	fmt.Println("== 窗口过期后同键再来（模拟 m3 长时间后才补投）==")
	now = now.Add(2 * time.Hour)
	feed(events[2]) // m3 已过期 → 允许再次生效

	fmt.Printf("\n副作用实际生效 %d 次（唯一事件 5 + 过期后补投 1）\n", sink.Count())
}
