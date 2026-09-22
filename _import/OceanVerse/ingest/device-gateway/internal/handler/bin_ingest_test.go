package handler

import (
	"bytes"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// goldenFrame 与 simframe 黄金样本一致的 58B 示例帧(0x08+0x09)
const goldenFrameHex = "232302fe" +
	"4f56323032363030303100000000000000" +
	"01" + "0021" +
	"1a09110c1e00" +
	"080101025a26dd00040001040ccc0cd00cc10cc7" +
	"0901010002474b" +
	"65"

func postBin(t *testing.T, h http.Handler, body, token string) *httptest.ResponseRecorder {
	t.Helper()
	r := httptest.NewRequest(http.MethodPost, "/api/v1/bin/ingest", strings.NewReader(body))
	if token != "" {
		r.Header.Set("X-Webhook-Token", token)
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	return w
}

func TestBinIngest_OK(t *testing.T) {
	fs := &fakeSender{}
	h := NewBinIngestHandler(fs, "test-secret")

	frame, _ := hex.DecodeString(goldenFrameHex)
	body := `{"clientid":"dev-OV20260001","topic":"ov/OV20260001/bin","ts":1789619400123,"payload_b64":"` +
		base64.StdEncoding.EncodeToString(frame) + `"}`
	w := postBin(t, http.HandlerFunc(h.IngestBin), body, "test-secret")

	if w.Code != http.StatusNoContent {
		t.Fatalf("期望 204, 实际 %d, body=%s", w.Code, w.Body)
	}
	if len(fs.messages) != 1 {
		t.Fatalf("应投递 1 条, 实际 %d", len(fs.messages))
	}
	if fs.messages[0].key != "OV20260001" {
		t.Errorf("Kafka key 应为 VIN, 实际 %q", fs.messages[0].key)
	}
	// 信封字段齐全且 cmd 窥自帧头第 3 字节
	var env rawEnvelope
	if err := json.Unmarshal([]byte(fs.messages[0].payload), &env); err != nil {
		t.Fatalf("信封应为合法 JSON: %v", err)
	}
	if env.VIN != "OV20260001" || env.ProtoVer != "v1" || env.Cmd != 0x02 || env.Ts != 1789619400 {
		t.Errorf("信封字段不符: %+v", env)
	}
	raw, err := base64.StdEncoding.DecodeString(env.Payload)
	if err != nil || len(raw) != 58 {
		t.Errorf("payload 应为 58B 原始帧, 实际 len=%d err=%v", len(raw), err)
	}
}

func TestBinIngest_Unauthorized(t *testing.T) {
	fs := &fakeSender{}
	h := NewBinIngestHandler(fs, "test-secret")
	w := postBin(t, http.HandlerFunc(h.IngestBin), `{}`, "wrong-secret")
	if w.Code != http.StatusUnauthorized {
		t.Errorf("错误密钥应 401, 实际 %d", w.Code)
	}
	if len(fs.messages) != 0 {
		t.Error("未授权请求不应投递")
	}
}

func TestBinIngest_BadTopic(t *testing.T) {
	fs := &fakeSender{}
	h := NewBinIngestHandler(fs, "test-secret")
	body := `{"clientid":"x","topic":"ov/ABC/status","ts":1,"payload_b64":"IyM="}`
	w := postBin(t, http.HandlerFunc(h.IngestBin), body, "test-secret")
	if w.Code != http.StatusBadRequest {
		t.Errorf("非 bin topic 应 400, 实际 %d", w.Code)
	}
}

func TestBinIngest_BadBase64(t *testing.T) {
	fs := &fakeSender{}
	h := NewBinIngestHandler(fs, "test-secret")
	body := `{"clientid":"dev-OV20260001","topic":"ov/OV20260001/bin","ts":1,"payload_b64":"!!!not-base64!!!"}`
	w := postBin(t, http.HandlerFunc(h.IngestBin), body, "test-secret")
	if w.Code != http.StatusBadRequest {
		t.Errorf("非法 base64 应 400, 实际 %d", w.Code)
	}
	if len(fs.messages) != 0 {
		t.Error("非法载荷不应投递")
	}
}

// goldenFullFrame 全信息体黄金帧(142B: 0x01+0x05+0x06+0x07+0x08+0x09+0x80+0x81,
// 由 simulator 模块的 simframe 生成后固化——gateway 不能 import 它的 internal,
// 跨模块对拍由端到端联调承担, 本测试只验透传字节无损)
const goldenFullFrameHex = "232302fe4f5632303236303030310000000000000001" +
	"00751a09110c1e00" +
	"010103ff01450001e2404effffffffffff" + // 0x01 整车
	"050006ca96200157eee0" + // 0x05 位置
	"06ffffffffffffffffffff4bffff44" + // 0x06 极值
	"07010000000001000e1001000000" + // 0x07 报警(E1001)
	"080101025a26dd00020001020ccc0cd0" + // 0x08 电压(2 节)
	"0901010002474b" + // 0x09 温度
	"8001000f002d00960050000004000000005803" + // 0x80 charging
	"81010009010304b0007d03203c" + // 0x81 工况
	"33" // BCC

// TestBinIngest_FullFrameRoundtrip 全信息体帧经透传后必须逐字节无损(透传纪律: 不解帧)
func TestBinIngest_FullFrameRoundtrip(t *testing.T) {
	fs := &fakeSender{}
	h := NewBinIngestHandler(fs, "test-secret")

	frame, err := hex.DecodeString(goldenFullFrameHex)
	if err != nil {
		t.Fatal(err)
	}
	body := `{"clientid":"dev-OV20260001","topic":"ov/OV20260001/bin","ts":1789619400123,"payload_b64":"` +
		base64.StdEncoding.EncodeToString(frame) + `"}`
	w := postBin(t, http.HandlerFunc(h.IngestBin), body, "test-secret")
	if w.Code != http.StatusNoContent {
		t.Fatalf("全信息体帧应透传成功(204), 实际 %d, body=%s", w.Code, w.Body)
	}
	if len(fs.messages) != 1 {
		t.Fatalf("应投递 1 条, 实际 %d", len(fs.messages))
	}
	var env rawEnvelope
	if err := json.Unmarshal([]byte(fs.messages[0].payload), &env); err != nil {
		t.Fatal(err)
	}
	got, err := base64.StdEncoding.DecodeString(env.Payload)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(got, frame) {
		t.Errorf("透传后帧内容必须逐字节一致:\n got %x\nwant %x", got, frame)
	}
	if env.Cmd != 0x02 || env.VIN != "OV20260001" {
		t.Errorf("信封字段不符: %+v", env)
	}
}
