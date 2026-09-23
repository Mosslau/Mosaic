// 来源：ph19-mq-event-driven exercises/sol-01-kafka-consumer-device-data（练习 1 参考实现）
// 一句话说明：telemetry 事件载体——与 examples/ex01/ex02 同构的最小版（离线模拟
// Kafka 消息：key=deviceID、value=JSON）。在真实 Kafka 里 value 用同一份 JSON，
// 用 kafka-go 拉取的 Reader 只是把消息喂进 handle 的前置环节（见文件尾"真 broker 切换"）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

// Telemetry 一条设备遥测（JSON 载荷；字段只增不删见 examples/ex04 的 schema 纪律）。
type Telemetry struct {
	DeviceID string  `json:"deviceId"`
	TS        int64   `json:"ts"`    // unix 秒
	Speed     float64 `json:"speed"` // km/h
	Component   int     `json:"component"`
}
