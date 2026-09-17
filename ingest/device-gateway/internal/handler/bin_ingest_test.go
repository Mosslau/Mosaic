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
	"time"

	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/simframe"
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

// TestBinIngest_SimframeRoundtrip 造帧器 → webhook 信封 → Kafka 信封 全链路往返:
// 模拟器(simframe)产的帧经本 handler 透传后必须逐字节无损(透传纪律: 不解帧)
func TestBinIngest_SimframeRoundtrip(t *testing.T) {
	fs := &fakeSender{}
	h := NewBinIngestHandler(fs, "test-secret")

	// 用 simframe 造一帧全信息体(0x01+0x05+0x06+0x07+0x08+0x09+0x80+0x81)
	now := time.Now()
	frame := simframe.Frame(simframe.CmdRealtime, simframe.AckNone, "OV20260001",
		simframe.DataUnit(now,
			simframe.BodyVehicle(simframe.VehicleBody{VehicleStatus: 0x01, ChargeStatus: 0x03, SpeedKmh: 32.5, OdometerKm: 12345.6, SOC: 78}),
			simframe.BodyPosition(113.94, 22.54),
			simframe.BodyExtremes(35, 28),
			simframe.BodyAlarm(0x01, []uint32{0xE1001}),
			simframe.BodyBatteryVolt(simframe.BatteryVoltBody{Voltage: 60.2, Current: -5.1, CellVoltages: []float64{3.276, 3.28}}),
			simframe.BodyBatteryTemp([]float64{31, 35}),
			simframe.BodyCharging(simframe.ChargingBody{RemainMin: 45, PowerKW: 1.5, EnergyKWh: 0.8, PileID: 1024, StationID: 88, SlotNo: 3}),
			simframe.BodyWork(simframe.WorkBody{RideState: simframe.RideRiding, RideMode: simframe.ModeSport, MotorRPM: 1200, MotorTorque: 12.5, MotorPower: 800, Throttle: 60}),
		))

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
