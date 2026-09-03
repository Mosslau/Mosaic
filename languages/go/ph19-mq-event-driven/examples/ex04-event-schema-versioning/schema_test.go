// 来源：ph19-mq-event-driven examples/ex04-event-schema-versioning/schema_test.go
// 一句话说明：事件 schema 演进纪律的断言——老消费者读新事件无损、字段只增不删、
// 删/改字段是静默破坏、未知未来版本必须显式拒绝。这与 ph18 ex06 的 protobuf
// 兼容实验是同一张纪律表在消息队列侧的落地（主文档 3.8）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"errors"
	"testing"
)

func mustEnvelope(t *testing.T, msgID string, version int, payload any) Envelope {
	t.Helper()
	env, err := BuildEnvelope(msgID, "telemetry", version, payload)
	if err != nil {
		t.Fatal(err)
	}
	return env
}

// TestOldConsumerReadsNewEvent 老消费者（v1 视角）解析 v2 事件成功且老字段完好。
func TestOldConsumerReadsNewEvent(t *testing.T) {
	v2 := mustEnvelope(t, "e1", SchemaV2, TelemetryV2{
		TelemetryV1: TelemetryV1{VehicleID: "car-001", TS: 101, Speed: 55},
		Lat:         31.23,
		Lng:         121.47,
	})
	got, err := ParseTelemetryV1(v2.Data)
	if err != nil {
		t.Fatalf("old consumer must tolerate new event: %v", err)
	}
	if got.VehicleID != "car-001" || got.Speed != 55 {
		t.Fatalf("old fields broken: %+v", got)
	}
}

// TestNewConsumerReadsOldEvent 新消费者（v2 视角）解析 v1 老事件：新增字段落零值。
func TestNewConsumerReadsOldEvent(t *testing.T) {
	v1 := mustEnvelope(t, "e1", SchemaV1, TelemetryV1{VehicleID: "car-001", TS: 100, Speed: 50})
	got, err := ParseTelemetryV2(v1.Data)
	if err != nil {
		t.Fatal(err)
	}
	if got.Lat != 0 || got.Lng != 0 {
		t.Fatalf("missing new fields must be zero: %+v", got)
	}
}

// TestEnvelopeRoundTrip 信封往返无损（mid/type/schemaVersion 透传）。
func TestEnvelopeRoundTrip(t *testing.T) {
	env := mustEnvelope(t, "e-round", SchemaV2, TelemetryV2{})
	b, err := json.Marshal(env)
	if err != nil {
		t.Fatal(err)
	}
	back, err := ParseEnvelope(b)
	if err != nil {
		t.Fatal(err)
	}
	if back.MsgID != "e-round" || back.Type != "telemetry" || back.SchemaVersion != SchemaV2 {
		t.Fatalf("roundtrip mismatch: %+v", back)
	}
}

// TestUnknownVersionRejected 未来版本必须显式拒绝，不猜语义。
func TestUnknownVersionRejected(t *testing.T) {
	v9 := mustEnvelope(t, "e9", 9, map[string]any{"x": 1})
	if err := CheckSupported(v9, map[int]bool{SchemaV1: true, SchemaV2: true}); !errors.Is(err, ErrUnknownVersion) {
		t.Fatalf("want ErrUnknownVersion, got %v", err)
	}
	// 已登记的版本放行
	v2 := mustEnvelope(t, "e2", SchemaV2, TelemetryV2{})
	if err := CheckSupported(v2, map[int]bool{SchemaV1: true, SchemaV2: true}); err != nil {
		t.Fatalf("v2 must pass: %v", err)
	}
}

// TestFieldRenameIsSilentBreak 字段改名 = 删除旧字段 + 新增新字段：解码"成功"但
// 数据静默丢失（lat→0）。这正是事件 schema 上禁止改名的原因——它不报错。
func TestFieldRenameIsSilentBreak(t *testing.T) {
	renamed := mustEnvelope(t, "e4", SchemaV2,
		map[string]any{"vehicleId": "car-001", "ts": 102, "speed": 60, "latitude": 31.5})
	got, err := ParseTelemetryV2(renamed.Data)
	if err != nil {
		t.Fatalf("parse succeeds syntactically: %v", err)
	}
	if got.Speed != 60 {
		t.Fatalf("speed should survive: %+v", got)
	}
	if got.Lat != 0 {
		t.Fatalf("renamed field must lose data (lat=%v, want 0) —— 证明改名是静默破坏", got.Lat)
	}
}

// TestFieldDeleteIsBreaking 删字段同样静默：老数据里没有该键，新消费者读零值。
func TestFieldDeleteIsBreaking(t *testing.T) {
	// 模拟："v3 删掉了 lng" —— 事件里没有 lng 键
	data := []byte(`{"vehicleId":"car-001","ts":103,"speed":70,"lat":31.5}`)
	got, err := ParseTelemetryV2(data)
	if err != nil {
		t.Fatal(err)
	}
	if got.Lng != 0 {
		t.Fatalf("deleted field reads zero: %+v", got)
	}
	_ = data
}
