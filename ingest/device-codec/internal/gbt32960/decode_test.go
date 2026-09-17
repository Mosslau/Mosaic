package gbt32960

import (
	"encoding/hex"
	"testing"
)

// golden 58B 示例帧(与 simframe 黄金样本/映射文档示例一致): 0x08 + 0x09
const goldenFrameHex = "232302fe" +
	"4f56323032363030303100000000000000" +
	"01" + "0021" +
	"1a09110c1e00" +
	"080101025a26dd00040001040ccc0cd00cc10cc7" +
	"0901010002474b" +
	"65"

func mustHex(t *testing.T, s string) []byte {
	t.Helper()
	b, err := hex.DecodeString(s)
	if err != nil {
		t.Fatalf("测试样本 hex 非法: %v", err)
	}
	return b
}

// TestParseFrame_Golden 包头轻解析: 帧同步/VIN 去填充/命令字/BCC(§2)
func TestParseFrame_Golden(t *testing.T) {
	f, err := ParseFrame(mustHex(t, goldenFrameHex))
	if err != nil {
		t.Fatalf("黄金样本应解析成功: %v", err)
	}
	if f.Cmd != 0x02 || f.Ack != 0xFE {
		t.Errorf("命令单元应为 02 fe, 实际 %02x %02x", f.Cmd, f.Ack)
	}
	if f.VIN != "OV20260001" {
		t.Errorf("VIN 应去填充为 OV20260001, 实际 %q", f.VIN)
	}
	if len(f.Data) != 33 {
		t.Errorf("数据单元应 33B, 实际 %d", len(f.Data))
	}
}

// TestDecode_Golden 黄金样本解码: 0x08+0x09 → 一条 battery_status(§8-④)
func TestDecode_Golden(t *testing.T) {
	f, err := ParseFrame(mustHex(t, goldenFrameHex))
	if err != nil {
		t.Fatal(err)
	}
	reports, dlq, err := DecodeV1(f)
	if err != nil || len(dlq) != 0 {
		t.Fatalf("应无错误无 DLQ: err=%v dlq=%v", err, dlq)
	}
	if len(reports) != 1 {
		t.Fatalf("应合并为 1 条 battery_status, 实际 %d 条", len(reports))
	}
	r := reports[0]
	if r.Type != "battery_status" || r.VIN != "OV20260001" || r.SchemaVersion != "v1" {
		t.Errorf("信封字段不符: %+v", r)
	}
	if r.Ts != 1789619400 { // 2026-09-17 12:30:00 GMT+8
		t.Errorf("ts 应为 1789619400, 实际 %d", r.Ts)
	}
	if *r.Data.Voltage != 60.2 || *r.Data.Current != -5.1 {
		t.Errorf("电压/电流解码错误: %v %v", *r.Data.Voltage, *r.Data.Current)
	}
	wantCells := []float64{3.276, 3.280, 3.265, 3.271}
	if len(r.Data.CellVoltages) != 4 {
		t.Fatalf("应有 4 节单体, 实际 %d", len(r.Data.CellVoltages))
	}
	for i, v := range wantCells {
		if r.Data.CellVoltages[i] != v {
			t.Errorf("单体[%d] 应为 %v, 实际 %v", i, v, r.Data.CellVoltages[i])
		}
	}
	if len(r.Data.ProbeTemps) != 2 || r.Data.ProbeTemps[0] != 31 || r.Data.ProbeTemps[1] != 35 {
		t.Errorf("探针温度应为 [31 35], 实际 %v", r.Data.ProbeTemps)
	}
}

// TestParseFrame_BCC 校验失败 → 帧级错误(整帧 DLQ)
func TestParseFrame_BCC(t *testing.T) {
	raw := mustHex(t, goldenFrameHex)
	raw[len(raw)-1] ^= 0xFF // 破坏 BCC
	if _, err := ParseFrame(raw); err == nil {
		t.Error("BCC 错误应检出")
	}
}

// TestParseFrame_Sync 起始符错误 → 帧同步失败
func TestParseFrame_Sync(t *testing.T) {
	raw := mustHex(t, goldenFrameHex)
	raw[0] = 0x00
	if _, err := ParseFrame(raw); err == nil {
		t.Error("起始符错误应检出")
	}
}

// TestDecode_CustomUnits 0x80/0x81 解码(§5.2): 枚举翻译 + 有符号值 + 无效值丢弃
func TestDecode_CustomUnits(t *testing.T) {
	// 数据单元: 时间 + 0x80(15B) + 0x81(9B)
	du := mustHex(t,
		"1a09110c1e00"+ // 时间
			"8001"+"000f"+ // 0x80 统一头 v1, 15B
			"002d"+"0096"+"0050"+"00000400"+"00000058"+"03"+ // 45min, 1.5kW, 0.8kWh, 桩1024, 站88, 仓3
			"8101"+"0009"+ // 0x81 统一头 v1, 9B
			"01"+"03"+"04b0"+"ffdd"+"fe48"+"3c") // 行驶/运动/1200rpm/-3.5N·m/-440W/60%
	f := &Frame{Cmd: 0x02, VIN: "OV20260001", Data: du}
	reports, dlq, err := DecodeV1(f)
	if err != nil || len(dlq) != 0 {
		t.Fatalf("应无错误无 DLQ: err=%v dlq=%v", err, dlq)
	}
	if len(reports) != 2 {
		t.Fatalf("应输出 charging + work 两条, 实际 %d", len(reports))
	}
	var charging, work = reports[0], reports[1]
	if reports[0].Type == "work" {
		charging, work = reports[1], reports[0]
	}
	if charging.Type != "charging" {
		t.Fatalf("应有 charging 类型, 实际 %s", charging.Type)
	}
	if *charging.Data.RemainChargeMin != 45 || *charging.Data.PileID != 1024 ||
		*charging.Data.StationID != 88 || *charging.Data.SlotNo != 3 {
		t.Errorf("charging 字段解码错误: %+v", charging.Data)
	}
	if *charging.Data.ChargePower != 1.5 || *charging.Data.ChargeKWh != 0.8 {
		t.Errorf("charging 功率/电量解码错误: %v %v", *charging.Data.ChargePower, *charging.Data.ChargeKWh)
	}
	if work.Type != "work" {
		t.Fatalf("应有 work 类型, 实际 %s", work.Type)
	}
	if *work.Data.RideState != "riding" || *work.Data.RideMode != "sport" {
		t.Errorf("枚举翻译错误: %v %v", *work.Data.RideState, *work.Data.RideMode)
	}
	if *work.Data.MotorRPM != 1200 || *work.Data.MotorTorque != -3.5 || *work.Data.MotorPower != -440 || *work.Data.Throttle != 60 {
		t.Errorf("work 数值解码错误: %+v", work.Data)
	}
}

// TestDecode_UnknownCustomVersion 未知自定义单元版本 → 单元级 DLQ(版本纪律: 不猜), 帧其余部分不受影响
func TestDecode_UnknownCustomVersion(t *testing.T) {
	du := mustHex(t,
		"1a09110c1e00"+
			"8002"+"000f"+"002d00960050000004000000005803") // 0x80 但版本 v2
	f := &Frame{Cmd: 0x02, VIN: "OV20260001", Data: du}
	reports, dlq, err := DecodeV1(f)
	if err != nil {
		t.Fatalf("单元级失败不应升级为帧级错误: %v", err)
	}
	if len(reports) != 0 {
		t.Errorf("未知版本单元不应产出, 实际 %d 条", len(reports))
	}
	if len(dlq) != 1 || dlq[0].UnitType != 0x80 {
		t.Fatalf("应有 1 条 0x80 单元 DLQ, 实际 %+v", dlq)
	}
}
