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
// 必须整帧拒绝、零产出 —— 不能因为"没有身份"就放行。
//
// stage 归属(2026-09-20 明确): 空 VIN **先被契约校验拦下**(stage=vin_invalid), 而不是
// vin_mismatch —— 前者说"这个 VIN 本身不合契约", 后者说"两个合法 VIN 对不上",
// 排障时两者的处置完全不同(前者查 topic/ACL 配置, 后者按安全事件查凭证滥用)。
func TestProcess_VINEmptyEnvelopeRejected(t *testing.T) {
	reports, dlqs := process(envelope(t, "", mustGoldenFrame(t)))

	if len(reports) != 0 {
		t.Fatalf("信封 VIN 为空时不得产出 report, 实际 %d 条", len(reports))
	}
	if len(dlqs) != 1 || dlqs[0].Stage != "vin_invalid" {
		t.Fatalf("应 1 条 vin_invalid DLQ, 实际 %+v", dlqs)
	}
	if !strings.Contains(dlqs[0].Reason, "5~32") {
		t.Errorf("reason 应说明契约边界, 实际 %q", dlqs[0].Reason)
	}
}

// TestProcess_FrameVINTooShortRejected 帧内 VIN 不合契约长度 → vin_invalid, 零产出。
// 背景(2026-09-20 修复的不对称): 网关侧三条通道都跑 vehicle.Validate()(VIN 5~32),
// 但二进制通道的 VIN 来自**帧内字节**, 此前只判"与信封一致" —— 一个 3 字节的 VIN
// 只要与信封一致就能一路产出成合法 L2 数据。现在两侧用同一组边界。
//
// 样本构造上的一个**真实约束**: 帧内 VIN 字段只有 17 字节, 所以"超长"这一类
// (18~32)在物理上无法出现在帧内 —— 需要覆盖的那一侧是**信封** VIN 超长(见下一条用例)。
func TestProcess_FrameVINTooShortRejected(t *testing.T) {
	frame := mustGoldenFrame(t)
	short := "OV1" // 3 字符 < VINMinLen(5)
	rewritten := rewriteFrameVIN(t, frame, short)

	// 信封用**合法** VIN, 如此才真的走到"帧内 VIN 不合契约"这条分支
	// (若信封也不合法, 会在信封校验处先被拦下, 测不到帧内这条)
	reports, dlqs := process(envelope(t, "OV00000001", rewritten))

	if len(reports) != 0 {
		t.Fatalf("VIN 不合契约时不得产出, 实际 %d 条: %+v", len(reports), reports)
	}
	if len(dlqs) != 1 || dlqs[0].Stage != "vin_invalid" {
		t.Fatalf("应 1 条 vin_invalid DLQ, 实际 %+v", dlqs)
	}
	if !strings.Contains(dlqs[0].Reason, "帧内 VIN") {
		t.Errorf("reason 应指明是帧内 VIN 不合契约, 实际 %q", dlqs[0].Reason)
	}
	if dlqs[0].RawB64 == "" {
		t.Error("DLQ 应保留原始帧(取证需要)")
	}
}

// TestProcess_EnvelopeVINTooLongRejected 信封 VIN 超长(>32) → vin_invalid。
// 这一条覆盖"帧内装不下"的那一侧: 帧字段只有 17 字节, 所以超长只可能来自 topic/信封。
func TestProcess_EnvelopeVINTooLongRejected(t *testing.T) {
	frame := mustGoldenFrame(t)
	long := strings.Repeat("A", 33) // 帧内 VIN 保持合法, 只有信封超长
	envelopeVIN := long

	reports, dlqs := process(envelope(t, envelopeVIN, frame))
	if len(reports) != 0 || len(dlqs) != 1 || dlqs[0].Stage != "vin_invalid" {
		t.Fatalf("超长信封 VIN 应进 vin_invalid DLQ 且零产出, got reports=%d dlqs=%+v", len(reports), dlqs)
	}
	if !strings.Contains(dlqs[0].Reason, "信封") {
		t.Errorf("reason 应指明是信封 VIN 不合契约, 实际 %q", dlqs[0].Reason)
	}
}

// TestProcess_VINBoundaryAccepted 契约边界值必须放行 —— 防止"修不对称"时矫枉过正
// 把合法设备拦下。上界取**帧字段的物理上限 17**(帧内 VIN 最长只能 17 字节;
// 契约上界 32 只可能出现在信封侧, 见上一条用例)。
func TestProcess_VINBoundaryAccepted(t *testing.T) {
	for _, vin := range []string{
		"OV123",                 // 下界 = VINMinLen(5)
		strings.Repeat("A", 17), // 帧字段物理上界
	} {
		frame := rewriteFrameVIN(t, mustGoldenFrame(t), vin)
		reports, dlqs := process(envelope(t, vin, frame))
		if len(dlqs) != 0 {
			t.Errorf("边界 VIN %q(长度 %d) 不应进 DLQ: %+v", vin, len(vin), dlqs)
		}
		if len(reports) == 0 {
			t.Errorf("边界 VIN %q 应正常产出", vin)
		}
	}
}

// rewriteFrameVIN 把帧内 VIN 字段(偏移 4..21)改写为给定 VIN 并重算 BCC。
// 用于构造"帧内 VIN 不合契约"的样本 —— 样本必须是**结构合法**的帧,
// 否则会先被 ParseFrame 拦下, 测不到 VIN 契约校验这条路径。
func rewriteFrameVIN(t *testing.T, frame []byte, vin string) []byte {
	t.Helper()
	if len(vin) > 17 {
		t.Fatalf("VIN 超过帧字段长度 17: %d", len(vin))
	}
	out := make([]byte, len(frame))
	copy(out, frame)
	for i := 4; i < 21; i++ {
		out[i] = 0x00
	}
	copy(out[4:21], vin)
	var bcc byte
	for _, b := range out[2 : len(out)-1] {
		bcc ^= b
	}
	out[len(out)-1] = bcc
	return out
}
