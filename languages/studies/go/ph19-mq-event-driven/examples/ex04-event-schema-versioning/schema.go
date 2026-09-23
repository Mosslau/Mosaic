// 来源：ph19-mq-event-driven examples/ex04-event-schema-versioning/schema.go
// 一句话说明：事件 schema 版本管理的最小机制——ph18 把"字段只增不删"用在
// REST 响应上，这里的消费者同样是"客户端"：一个 topic 上 producer 先升级了
// schema，落后版本的 consumer 必须还能解析（主文档 3.8）。
// 载荷用带 schemaVersion 的信封（envelope）承载，老消费者靠"JSON 忽略未知
// 字段"天然容忍新增字段——与 ph18 ex06 的 protobuf 未知字段号跳过互为镜像。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"errors"
	"fmt"
)

// Schema 版本号：topic 里的事件 schema 从 v1 演进到 v2（只追加）。
const (
	SchemaV1 = 1
	SchemaV2 = 2
)

// ErrUnknownVersion 哨兵：遇到"未来的、消费者没登记过的"版本。
// 真实工程的处理是把原始消息（raw）转存，等配套消费者上线后再补——
// 绝不拿错的 schema 硬解析出脏数据。
var ErrUnknownVersion = errors.New("event schema version not supported by this consumer")

// Envelope 事件信封：消息队列里"消息结构"的公共部分。
// type + schemaVersion 决定了 data 的解析规则——schema 版本号必须显式，
// 靠"猜字段形状"推断版本是事件演进里最常见的翻车现场。
type Envelope struct {
	MsgID         string          `json:"mid"`
	Type          string          `json:"type"`
	SchemaVersion int             `json:"schemaVersion"`
	Data          json.RawMessage `json:"data"`
}

// BuildEnvelope 打包一条事件：把 payload 序列化进 Data。
func BuildEnvelope(msgID, typ string, version int, payload any) (Envelope, error) {
	raw, err := json.Marshal(payload)
	if err != nil {
		return Envelope{}, fmt.Errorf("marshal payload: %w", err)
	}
	return Envelope{
		MsgID:         msgID,
		Type:          typ,
		SchemaVersion: version,
		Data:          raw,
	}, nil
}

// ParseEnvelope 解析收到的字节为信封（producer 端/consumer 端共用）。
func ParseEnvelope(b []byte) (Envelope, error) {
	var env Envelope
	if err := json.Unmarshal(b, &env); err != nil {
		return Envelope{}, fmt.Errorf("parse envelope: %w", err)
	}
	if env.SchemaVersion < 1 {
		return Envelope{}, fmt.Errorf("%w: schemaVersion=%d", ErrUnknownVersion, env.SchemaVersion)
	}
	return env, nil
}

// 版本化载荷：v2 = v1 超集（新增 lat/lng）。字段只增不删靠结构演进保证——
// 老消费者用 v1 结构解析 v2 数据时，多余字段被 JSON 解码器忽略。
type TelemetryV1 struct {
	DeviceID string  `json:"deviceId"`
	TS        int64   `json:"ts"`
	Speed     float64 `json:"speed"`
}

// TelemetryV2 内嵌 v1：字段天然继承，v2 只是追加，不重写老字段。
type TelemetryV2 struct {
	TelemetryV1
	Lat float64 `json:"lat"`
	Lng float64 `json:"lng"`
}

// ParseTelemetryV1 用 v1 视角解析任意版本事件的 data。
// 对 v2 数据同样成功：新增字段被忽略——老消费者向前兼容（producer 先行）。
func ParseTelemetryV1(data json.RawMessage) (TelemetryV1, error) {
	var v TelemetryV1
	if err := json.Unmarshal(data, &v); err != nil {
		return v, fmt.Errorf("decode as v1: %w", err)
	}
	return v, nil
}

// ParseTelemetryV2 用 v2 视角解析：v1 老数据缺 lat/lng 时落零值——
// 语义上"可用默认值兜底"还是"数据不完整"，由业务判定（见 Supported 注释）。
func ParseTelemetryV2(data json.RawMessage) (TelemetryV2, error) {
	var v TelemetryV2
	if err := json.Unmarshal(data, &v); err != nil {
		return v, fmt.Errorf("decode as v2: %w", err)
	}
	return v, nil
}

// CheckSupported 版本登记：消费者声明自己理解哪些 schemaVersion。
// 返回 ErrUnknownVersion 表示"这是未来版本的语义，本消费者不能猜"——
// 猜测 = 用旧结构解释新含义，是静默脏数据的来源。
func CheckSupported(env Envelope, supported map[int]bool) error {
	if !supported[env.SchemaVersion] {
		return fmt.Errorf("%w: %s v%d", ErrUnknownVersion, env.Type, env.SchemaVersion)
	}
	return nil
}
