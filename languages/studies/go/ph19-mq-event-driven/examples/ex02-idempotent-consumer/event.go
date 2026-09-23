// 来源：ph19-mq-event-driven examples/ex02-idempotent-consumer/event.go
// 一句话说明：事件载体——MsgID 是 producer 生成、全局唯一的幂等键（类比
// ph18 3.6 的 Idempotency-Key，这里落在消息 payload 上）。schema 版本等
// 信封字段见 ex04，本示例聚焦"重复消费"本身。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import "fmt"

// TelemetryEvent 一条设备遥测事件（简化：只保留与幂等相关的字段）。
type TelemetryEvent struct {
	MsgID     string  // 幂等键：一次"采样"的全局唯一 ID（重试/重投不变）
	DeviceID string  // 设备 ID
	TS        int64   // 采样时刻（unix 秒）
	Speed     float64 // 运行速度 km/h
}

// NewEvent 造一条带唯一 MsgID 的事件（演示/测试用）。
func NewEvent(device string, ts int64, speed float64, seq int) TelemetryEvent {
	return TelemetryEvent{
		MsgID:     fmt.Sprintf("%s-%d-%d", device, ts, seq),
		DeviceID: device,
		TS:        ts,
		Speed:     speed,
	}
}
