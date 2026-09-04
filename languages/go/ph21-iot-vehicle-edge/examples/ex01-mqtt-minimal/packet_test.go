// 来源：ph21-iot-vehicle-edge examples/ex01-mqtt-minimal/packet_test.go
// 一句话说明：报文层测试——变长剩余长度编解码、CONNECT/PUBLISH/SUBSCRIBE 编解码
// 往返、主题通配匹配、帧读取切帧。协议地基正确性自证。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"bytes"
	"errors"
	"reflect"
	"testing"
)

func TestRemainingLengthRoundTrip(t *testing.T) {
	for _, n := range []int{0, 1, 127, 128, 16383, 16384, 2097151, 2097152, 268435455} {
		enc, err := encodeRL(n)
		if err != nil {
			t.Fatalf("encodeRL(%d): %v", n, err)
		}
		got, used, err := decodeRL(enc)
		if err != nil {
			t.Fatalf("decodeRL(%d): %v", n, err)
		}
		if got != n || used != len(enc) {
			t.Errorf("RL(%d) → (%d, used=%d, len=%d)", n, got, used, len(enc))
		}
	}
}

func TestEncodeRLTooBig(t *testing.T) {
	if _, err := encodeRL(1 << 30); err == nil {
		t.Error("超上限剩余长度应报错")
	}
}

func TestConnectDecodeRoundTrip(t *testing.T) {
	in := connectPacket{ClientID: "veh-001", Username: "veh-001", Password: "tok-1", KeepAlive: 30}
	full := in.encode()
	typ, rest, err := readFrame(bytes.NewReader(full))
	if err != nil {
		t.Fatalf("readFrame: %v", err)
	}
	if typ != typeCONNECT {
		t.Fatalf("报文类型 = %d, want %d", typ, typeCONNECT)
	}
	got, err := decodeConnect(rest)
	if err != nil {
		t.Fatalf("decodeConnect: %v", err)
	}
	if !reflect.DeepEqual(got, in) {
		t.Errorf("CONNECT 往返不一致: got %+v want %+v", got, in)
	}
}

func TestConnectMissingProtocol(t *testing.T) {
	if _, err := decodeConnect([]byte{0, 0, 'X', 'Y', 'Z', 'W', 4, 2, 0, 0}); err == nil {
		t.Error("非 MQTT 协议名应报错")
	}
}

func TestPublishRoundTrip(t *testing.T) {
	in := publishPacket{Topic: "veh/veh-001/telemetry", Payload: []byte(`{"seq":7,"speed":66}`)}
	full := in.encode()
	typ, rest, err := readFrame(bytes.NewReader(full))
	if err != nil {
		t.Fatalf("readFrame: %v", err)
	}
	if typ != typePUBLISH {
		t.Fatalf("报文类型 = %d, want %d", typ, typePUBLISH)
	}
	got, err := decodePublish(rest)
	if err != nil {
		t.Fatalf("decodePublish: %v", err)
	}
	if got.Topic != in.Topic || !bytes.Equal(got.Payload, in.Payload) {
		t.Errorf("PUBLISH 往返不一致: got %+v want %+v", got, in)
	}
}

func TestSubscribeDecodeRoundTrip(t *testing.T) {
	in := subscribePacket{PacketID: 3, Filter: "veh/+/cmd"}
	full := in.encode()
	typ, rest, err := readFrame(bytes.NewReader(full))
	if err != nil {
		t.Fatalf("readFrame: %v", err)
	}
	if typ != typeSUBSCRIBE {
		t.Fatalf("报文类型 = %d, want %d", typ, typeSUBSCRIBE)
	}
	got, err := decodeSubscribe(rest)
	if err != nil {
		t.Fatalf("decodeSubscribe: %v", err)
	}
	if got.PacketID != 3 || got.Filter != "veh/+/cmd" {
		t.Errorf("SUBSCRIBE 往返不一致: got %+v", got)
	}
}

func TestTopicMatch(t *testing.T) {
	cases := []struct {
		filter, topic string
		want          bool
	}{
		{"veh/veh-001/telemetry", "veh/veh-001/telemetry", true},
		{"veh/veh-001/telemetry", "veh/veh-002/telemetry", false},
		{"veh/+/telemetry", "veh/veh-001/telemetry", true}, // + 匹配单层
		{"veh/+/telemetry", "veh/veh-001/cmd", false},      // 层级不同不命中
		{"veh/#", "veh/veh-001/telemetry", true},           // # 匹配剩余全部
		{"#", "anything/else", true},                       // 根 # 全匹配
		{"veh/+/telemetry", "veh/a/b/telemetry", false},    // + 只匹配一层
		{"veh/veh-001/#", "veh/veh-001", true},             // # 匹配零层
		{"veh/veh-001/#", "veh/veh-002/telemetry", false},
	}
	for _, c := range cases {
		if got := topicMatch(c.filter, c.topic); got != c.want {
			t.Errorf("topicMatch(%q, %q) = %v, want %v", c.filter, c.topic, got, c.want)
		}
	}
}

func TestErrNotAuthorizedIsError(t *testing.T) {
	if !errors.Is(ErrNotAuthorized, ErrNotAuthorized) {
		t.Error("哨兵错误应能被 errors.Is 命中")
	}
}

func TestReadFrameRejectsTruncated(t *testing.T) {
	// 固定头声明 100 字节负载但只给 3 字节 → io.ReadFull 应报错（不粘帧）。
	full := frame(typePUBLISH, 0, make([]byte, 100))
	if _, _, err := readFrame(bytes.NewReader(full[:5])); err == nil {
		t.Error("截断报文应报错")
	}
}
