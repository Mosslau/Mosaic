// 来源：ph19-mq-event-driven examples/ex02-idempotent-consumer/consumer.go
// 一句话说明：幂等消费循环——处理顺序是「查重 → 副作用 → 记账」。
// 副作用被去重表保护，重复投递的事件不会二次生效（主文档 3.5 去重表）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

// ProcessOnce 消费单条事件：已见过则跳过副作用；没见过则执行副作用并记账。
// 返回值 processed=true 表示副作用真实发生了一次。
func ProcessOnce(e TelemetryEvent, d *Deduper, apply func(TelemetryEvent)) bool {
	if d.Seen(e.MsgID) {
		return false // 重复投递：直接跳过，副作用不重放
	}
	apply(e)        // 副作用（落库/发下游/累加器）——只该发生一次
	d.Mark(e.MsgID) // 记账：本次成功处理过的键
	return true
}

// ProcessLog 依次处理一批事件，返回 (真实处理数, 去重跳过数)。
// 这模拟一个 partition 里的连续消息流：投递层可能重复（at-least-once），
// 本函数保证"每个 MsgID 的副作用至多一次"。
func ProcessLog(events []TelemetryEvent, d *Deduper, apply func(TelemetryEvent)) (processed, skipped int) {
	for _, e := range events {
		if ProcessOnce(e, d, apply) {
			processed++
		} else {
			skipped++
		}
	}
	return processed, skipped
}
