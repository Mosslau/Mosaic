package main

import (
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"strings"
	"testing"

	"github.com/Mosslau/OceanVerse/ingest/device-codec/internal/gbt32960"
)

// 本文件复用 flush_test.go 的 goldenFrameHex(同一 package main 的测试常量):
// 58B 黄金样本帧, 帧内 VIN = OV20260001。
// 为避免"VIN 写在注释里但和字节不符"这类漂移, 下面的用例**不硬编码 VIN** ——
// 一律用 frameVIN() 从帧里解出来。

// mustGoldenFrame 解码黄金样本帧, 并确认样本本身可被解析器接受
// (若样本损坏, 失败点应在这里, 而不是在下游的 VIN 断言上)。
func mustGoldenFrame(t *testing.T) []byte {
	t.Helper()
	b, err := hex.DecodeString(goldenFrameHex)
	if err != nil {
		t.Fatalf("黄金样本 hex 非法: %v", err)
	}
	return b
}

// frameVIN 从帧里解出 VIN(不硬编码, 避免注释与字节漂移)。
func frameVIN(t *testing.T, frame []byte) string {
	t.Helper()
	f, err := gbt32960.ParseFrame(frame)
	if err != nil {
		t.Fatalf("黄金样本应可解析: %v", err)
	}
	return f.VIN
}

// envelope 构造一条网关透传信封(topic VIN 由调用方给定)。
func envelope(t *testing.T, vin string, frame []byte) []byte {
	t.Helper()
	raw, err := json.Marshal(rawEnvelope{
		VIN:      vin,
		Ts:       1789619400,
		ProtoVer: "v1",
		Payload:  base64.StdEncoding.EncodeToString(frame),
	})
	if err != nil {
		t.Fatalf("信封序列化失败: %v", err)
	}
	return raw
}

// TestProcess_VINMatchAccepted 帧内 VIN == 信封 VIN 时正常产出。
// 这是**回归保护**: 新增的 VIN 校验不能把合法链路拦下来 ——
// bin-simulator 用同一个 vin 同时造帧与 topic(见其 main.go), 必须继续走通。
func TestProcess_VINMatchAccepted(t *testing.T) {
	frame := mustGoldenFrame(t)
	vin := frameVIN(t, frame)

	reports, dlqs := process(envelope(t, vin, frame))

	if len(dlqs) != 0 {
		t.Fatalf("合法帧不应进 DLQ, 实际 %+v", dlqs)
	}
	if len(reports) != 1 {
		t.Fatalf("应产出 1 条 report, 实际 %d", len(reports))
	}
	if reports[0].VIN != vin {
		t.Errorf("VIN 应为 %q, 实际 %q", vin, reports[0].VIN)
	}
}

// TestProcess_VINMismatchRejected 帧内 VIN ≠ 信封 VIN:
// 必须拒绝并进 DLQ, 且**一条 report 都不能产出** —— 这正是 EMQX ACL 被绕过的那条路径
// (设备用自己凭证发自己的 topic, 却在帧里填他人 VIN)。
func TestProcess_VINMismatchRejected(t *testing.T) {
	frame := mustGoldenFrame(t)
	victim := frameVIN(t, frame) // 帧内填的受害者 VIN
	attacker := "OV99999999"     // 设备自己凭证对应的 topic VIN

	reports, dlqs := process(envelope(t, attacker, frame))

	if len(reports) != 0 {
		t.Fatalf("帧内 VIN 与信封不一致时不得产出任何 report, 实际 %d 条: %+v", len(reports), reports)
	}
	if len(dlqs) != 1 {
		t.Fatalf("应恰好 1 条 DLQ, 实际 %d: %+v", len(dlqs), dlqs)
	}
	d := dlqs[0]
	if d.Stage != "vin_mismatch" {
		t.Errorf("stage 应为 vin_mismatch, 实际 %q", d.Stage)
	}
	// 安全溯源看"已认证的发送者", 故 DLQ 的 VIN 必须取信封(topic) VIN, 而不是帧内那个
	if d.VIN != attacker {
		t.Errorf("DLQ 的 VIN 应取信封 VIN %q, 实际 %q", attacker, d.VIN)
	}
	// 两个 VIN 都要留痕, 便于定位是谁冒充谁
	if !strings.Contains(d.Reason, attacker) || !strings.Contains(d.Reason, victim) {
		t.Errorf("Reason 应同时含信封(%s)与帧内(%s) VIN, 实际 %q", attacker, victim, d.Reason)
	}
	// 原始帧必须保留(事后取证)
	if d.RawB64 == "" {
		t.Error("DLQ 应保留原始帧 base64(取证需要)")
	}
}

// TestProcess_VINEmptyEnvelopeRejected 信封 VIN 为空(如有人绕过网关直接往 raw topic 灌消息):
// 帧内 VIN 非空 → 视为不一致, 同样拒绝。不能因为"没有身份"就放行。
func TestProcess_VINEmptyEnvelopeRejected(t *testing.T) {
	reports, dlqs := process(envelope(t, "", mustGoldenFrame(t)))

	if len(reports) != 0 {
		t.Fatalf("信封 VIN 为空时不得产出 report, 实际 %d 条", len(reports))
	}
	if len(dlqs) != 1 || dlqs[0].Stage != "vin_mismatch" {
		t.Fatalf("应 1 条 vin_mismatch DLQ, 实际 %+v", dlqs)
	}
}
