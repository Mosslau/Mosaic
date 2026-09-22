// 来源：ph19-mq-event-driven project/internal/model/model.go
// 一句话说明：遥测事件模型。载荷是带 schemaVersion 的信封（兑现 ph18 对
// "事件里的 schema 版本管理"的预告，机制见 examples/ex04）：消费者按版本
// 解码，未知未来版本显式拒绝而非猜语义。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package model

import (
	"encoding/json"
	"fmt"
)

// SchemaV1 当前消费服务支持的唯一 schema 版本（只增不删的演进从 v2 起，见 ex04）。
const SchemaV1 = 1

// Message 分区里的一条原始消息（fake broker 与消费者共享）。
type Message struct {
	Partition int
	Offset    int
	Key       string // = vehicleID，稳定散列决定分区 → 同车事件分区内有序
	Payload   []byte
}

// TelemetryEvent 遥测事件信封。MsgID 是幂等键（producer 保证全局唯一，
// at-least-once 重投时不变）——ph18 3.6 的 Idempotency-Key 在异步侧的兑现。
type TelemetryEvent struct {
	MsgID         string  `json:"mid"`
	SchemaVersion int     `json:"schemaVersion"`
	VehicleID     string  `json:"vehicleId"`
	TS            int64   `json:"ts"`    // unix 秒
	Speed         float64 `json:"speed"` // km/h
	Battery       int     `json:"battery"`
}

// Encode 序列化为消息载荷（producer 侧）。
func (e TelemetryEvent) Encode() ([]byte, error) {
	b, err := json.Marshal(e)
	if err != nil {
		return nil, fmt.Errorf("encode telemetry: %w", err)
	}
	return b, nil
}

// Decode 反序列化载荷为事件（纯 JSON 解析；schema 版本校验在处理层，见
// internal/process——"payload 能解析"与"版本受支持"是两个不同的失败）。
func Decode(payload []byte) (TelemetryEvent, error) {
	var e TelemetryEvent
	if err := json.Unmarshal(payload, &e); err != nil {
		return TelemetryEvent{}, fmt.Errorf("decode telemetry: %w", err)
	}
	return e, nil
}
